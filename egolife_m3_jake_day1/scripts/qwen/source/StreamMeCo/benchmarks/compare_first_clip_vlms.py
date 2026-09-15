#!/usr/bin/env python3
"""Run Qwen 3.5 and Gemini 3.8 concurrently from one shared clip context."""
import argparse
import ast
import json
import os
import pickle
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

from m3_agent.memorization_memory_graphs import memory_config
from mmagent.clip_audit import graph_delta, graph_identity, graph_view, write_json
from mmagent.face_processing import process_faces
from mmagent.memory_processing_qwen import generate_video_context, process_memories
from mmagent.prompts import prompt_generate_memory_with_ids_sft
from mmagent.utils.chat_api import parallel_get_embedding
from mmagent.utils.chat_gemini import generate_messages as gemini_messages
from mmagent.utils.chat_gemini import get_response_direct
from mmagent.utils.chat_qwen import generate_messages as qwen_messages
from mmagent.utils.chat_qwen import get_response as qwen_response
from mmagent.utils.general import validate_and_fix_json
from mmagent.utils.video_processing import process_video_clip
from mmagent.videograph import VideoGraph
from mmagent.voice_processing import process_voices

PROCESSING_CONFIG = json.loads((ROOT / "configs/processing_config.json").read_text())


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--clip", type=Path, required=True)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--clip-id", type=int, default=1)
    parser.add_argument("--gemini-fps", type=float, default=2.0)
    parser.add_argument("--gemini-max-pixels", type=int, default=151200)
    parser.add_argument("--qwen-max-attempts", type=int, default=3)
    parser.add_argument("--qwen-max-new-tokens", type=int, default=3072)
    return parser.parse_args()


def clone_graph(graph):
    return pickle.loads(pickle.dumps(graph))


def save_graph(graph, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("wb") as handle:
        pickle.dump(graph, handle)
    temp.replace(path)


def parse_memory_object(raw):
    parsed = validate_and_fix_json(raw)
    if isinstance(parsed, dict):
        return parsed
    text = raw.strip()
    decoder = json.JSONDecoder()
    for start, char in enumerate(text):
        if char != "{":
            continue
        try:
            candidate, _ = decoder.raw_decode(text[start:])
        except json.JSONDecodeError:
            continue
        if isinstance(candidate, dict):
            return candidate
    first, last = text.find("{"), text.rfind("}")
    if first >= 0 and last > first:
        try:
            candidate = ast.literal_eval(text[first:last + 1])
        except (SyntaxError, ValueError):
            pass
        else:
            if isinstance(candidate, dict):
                return candidate
    return None


def parse_memory(raw):
    parsed = parse_memory_object(raw)
    if not isinstance(parsed, dict):
        raise ValueError("VLM response is not a valid memory JSON object")
    episodic = parsed.get(
        "video_descriptions",
        parsed.get("video_description", parsed.get("episodic_memory")),
    )
    semantic = parsed.get(
        "high_level_conclusions", parsed.get("semantic_memory")
    )
    for label, values in (
        ("episodic memory", episodic),
        ("semantic memory", semantic),
    ):
        if not isinstance(values, list) or not values:
            raise ValueError(f"VLM response has no nonempty {label} list")
        if any(not isinstance(value, str) or not value.strip() for value in values):
            raise ValueError(f"VLM response {label} must contain only nonempty strings")
    return {
        "video_description": [value.strip() for value in episodic],
        "high_level_conclusions": [value.strip() for value in semantic],
    }


def run_qwen(messages, work, max_attempts, max_new_tokens):
    errors = []
    for attempt in range(1, max_attempts + 1):
        started = time.perf_counter()
        raw, tokens, details = qwen_response(
            messages, enable_thinking=True, max_new_tokens=max_new_tokens,
            return_details=True,
        )
        details.update({
            "attempt": attempt,
            "latency_ms": (time.perf_counter() - started) * 1000,
        })
        try:
            memory = parse_memory(raw)
        except ValueError as error:
            details["validation_error"] = str(error)
            errors.append(str(error))
        else:
            details["memory"] = memory
            write_json(work / f"qwen_attempt_{attempt}.json", details)
            return raw, tokens, details, memory
        write_json(work / f"qwen_attempt_{attempt}.json", details)
    raise ValueError(
        f"Qwen failed memory validation after {max_attempts} attempts: {errors}"
    )


def embed_memories(texts):
    if not texts:
        return [], 0.0, 0
    started = time.perf_counter()
    embeddings, tokens = parallel_get_embedding(
        "text-embedding-3-large", texts, timeout=120
    )
    return embeddings, (time.perf_counter() - started) * 1000, tokens


def run_branch(name, graph, messages, clip_id, run_started, before_nodes, before_edges,
               work, qwen_max_attempts, qwen_max_new_tokens):
    branch_started = time.perf_counter()
    if name == "qwen3.5-4b":
        vlm_started = time.perf_counter()
        raw, tokens, generation, memory = run_qwen(
            messages, work, qwen_max_attempts, qwen_max_new_tokens,
        )
        vlm_ms = (time.perf_counter() - vlm_started) * 1000
        usage = {"total_tokens": tokens}
        transport = "local NVIDIA RTX A6000"
    else:
        raw, tokens, vlm_ms, response = get_response_direct(messages)
        usage = response.get("usage")
        transport = "GPU-originated direct-IP 302.ai call"
        generation = None
        memory = parse_memory(raw)
    if memory["video_description"]:
        epi_embeddings, epi_embed_ms, epi_embed_tokens = embed_memories(
            memory["video_description"]
        )
    else:
        epi_embeddings, epi_embed_ms, epi_embed_tokens = [], 0.0, 0
    if memory["high_level_conclusions"]:
        sem_embeddings, sem_embed_ms, sem_embed_tokens = embed_memories(
            memory["high_level_conclusions"]
        )
    else:
        sem_embeddings, sem_embed_ms, sem_embed_tokens = [], 0.0, 0
    epi_metrics = {}
    sem_metrics = {}
    process_memories(
        graph, memory["video_description"], clip_id, type="episodic",
        metrics=epi_metrics, precomputed_embeddings=epi_embeddings,
        precomputed_embedding_ms=epi_embed_ms,
    )
    process_memories(
        graph, memory["high_level_conclusions"], clip_id, type="semantic",
        metrics=sem_metrics, precomputed_embeddings=sem_embeddings,
        precomputed_embedding_ms=sem_embed_ms,
    )
    refresh_started = time.perf_counter()
    graph.refresh_equivalences()
    equivalence_refresh_ms = (time.perf_counter() - refresh_started) * 1000
    readable = graph_view(graph)
    delta = graph_delta(graph, before_nodes, before_edges)
    insertion_ms = (
        epi_metrics.get("graph_update_ms", 0.0)
        + sem_metrics.get("graph_update_ms", 0.0)
    )
    return {
        "model": name,
        "transport": transport,
        "branch_ms": (time.perf_counter() - branch_started) * 1000,
        "end_to_end_memory_generation_ms": (time.perf_counter() - run_started) * 1000,
        "vlm_ms": vlm_ms,
        "text_embedding_ms": epi_embed_ms + sem_embed_ms,
        "graph_update_ms": insertion_ms + equivalence_refresh_ms,
        "graph_insertion_ms": insertion_ms,
        "equivalence_refresh_ms": equivalence_refresh_ms,
        "text_embedding_backend": {
            "provider": "OpenRouter",
            "endpoint": "https://openrouter.ai/api/v1/embeddings",
            "model": "openai/text-embedding-3-large",
        },
        "text_embedding_detail": {
            "episodic_ms": epi_embed_ms,
            "semantic_ms": sem_embed_ms,
            "episodic_tokens": epi_embed_tokens,
            "semantic_tokens": sem_embed_tokens,
        },
        "memory_processing": {"episodic": epi_metrics, "semantic": sem_metrics},
        "tokens": tokens,
        "usage": usage,
        "raw_memory": raw,
        "generation": generation,
        "memory": memory,
        "graph": readable,
        "graph_delta": delta,
        "graph_object": graph,
    }


def markdown(shared, branches):
    voice = shared["voice"]
    face = shared["face"]
    lines = [
        "# First Clip Memory Construction: Gemini 3.8 vs Qwen 3.5 4B", "",
        "## Shared preprocessing", "",
        "| Stage | Latency ms |", "| --- | ---: |",
        f"| Clip decode | {shared['clip_decode_ms']:.2f} |",
        f"| Deepgram ASR | {voice['asr_provider_ms'].get('deepgram-asr') or 0:.2f} |",
        f"| MAI-Transcribe-2 ASR | {voice['asr_provider_ms'].get('openrouter-mai-transcribe-2') or 0:.2f} |",
        f"| ASR total | {voice.get('asr_total_ms') or 0:.2f} |",
        f"| Audio segmentation | {voice.get('audio_segmentation_ms') or 0:.2f} |",
        f"| CAM++ speech embedding | {voice.get('speech_embedding_ms') or 0:.2f} |",
        f"| Buffalo-L detection + recognition | {face.get('face_detection_recognition_ms') or 0:.2f} |",
        f"| Face clustering | {face.get('face_clustering_ms') or 0:.2f} |",
        f"| VLM context construction | {shared['context_ms']:.2f} |",
        f"| Shared preprocessing wall time | {shared['shared_preprocess_ms']:.2f} |",
        "", "## Branch comparison", "",
        "Text embeddings: OpenRouter `openai/text-embedding-3-large` via `/api/v1/embeddings`.", "",
        "| Model | VLM ms | Text embed ms | Insert ms | Equivalence ms | Graph total ms | Branch ms | Clip-to-graph ms | Nodes | Edges |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for branch in branches:
        lines.append(
            f"| {branch['model']} | {branch['vlm_ms']:.2f} | {branch['text_embedding_ms']:.2f} | "
            f"{branch['graph_insertion_ms']:.2f} | {branch['equivalence_refresh_ms']:.2f} | "
            f"{branch['graph_update_ms']:.2f} | {branch['branch_ms']:.2f} | "
            f"{branch['end_to_end_memory_generation_ms']:.2f} | "
            f"{branch['graph']['counts']['nodes']} | {branch['graph']['counts']['edges']} |"
        )
    for branch in branches:
        raw_memory = branch["raw_memory"].strip()
        if raw_memory.startswith("```") and raw_memory.endswith("```"):
            raw_memory = "\n".join(raw_memory.splitlines()[1:-1])
        lines.extend([
            "", f"## {branch['model']} memory", "", "### Raw VLM response", "",
            "```json", raw_memory, "```", "", "### Video descriptions", "",
        ])
        lines.extend(f"- {value}" for value in branch["memory"]["video_description"])
        lines.extend(["", "### High-level conclusions", ""])
        lines.extend(f"- {value}" for value in branch["memory"]["high_level_conclusions"])
        lines.extend(["", "### Graph delta", "", "```json", json.dumps(branch["graph_delta"], ensure_ascii=False, indent=2), "```"])
        lines.extend(["", "### Actual nodes", "", "```json", json.dumps(branch["graph"]["nodes"], ensure_ascii=False, indent=2), "```"])
        lines.extend(["", "### Actual edges", "", "```json", json.dumps(branch["graph"]["edges"], ensure_ascii=False, indent=2), "```"])
    return "\n".join(lines) + "\n"


def main():
    args = parse_args()
    args.results.mkdir(parents=True, exist_ok=True)
    args.work.mkdir(parents=True, exist_ok=True)
    for name in ("fresh_voices.json", "fresh_faces.json"):
        (args.work / name).unlink(missing_ok=True)
    run_started = time.perf_counter()
    graph = VideoGraph(**memory_config)
    before_nodes, before_edges = graph_identity(graph)
    decode_started = time.perf_counter()
    base64_video, frames, audio = process_video_clip(str(args.clip), fps=PROCESSING_CONFIG["fps"])
    clip_decode_ms = (time.perf_counter() - decode_started) * 1000
    voice_metrics = {}
    voices = process_voices(
        graph, audio, base64_video, save_path=str(args.work / "fresh_voices.json"),
        preprocessing=[], metrics=voice_metrics,
    )
    face_metrics = {}
    faces = process_faces(
        graph, frames, save_path=str(args.work / "fresh_faces.json"),
        preprocessing=[], metrics=face_metrics,
    )
    context_started = time.perf_counter()
    context = generate_video_context(frames, faces, voices, video_path=str(args.clip))
    inputs = [{"type": "text", "content": prompt_generate_memory_with_ids_sft}] + context
    qwen_input = qwen_messages(inputs)
    gemini_input, gemini_media = gemini_messages(inputs, fps=args.gemini_fps, max_pixels=args.gemini_max_pixels)
    context_ms = (time.perf_counter() - context_started) * 1000
    shared_preprocess_ms = (time.perf_counter() - run_started) * 1000
    shared = {
        "clip": str(args.clip), "clip_decode_ms": clip_decode_ms,
        "voice": voice_metrics, "face": face_metrics,
        "context_ms": context_ms, "shared_preprocess_ms": shared_preprocess_ms,
        "gemini_media": gemini_media,
        "counts": {"preprocess_frames": len(frames), "voice_identities": len(voices), "face_identities": len(faces)},
    }
    write_json(args.results / "shared_preprocessing.json", shared)
    base_graph = clone_graph(graph)
    with ThreadPoolExecutor(max_workers=2) as executor:
        qwen_future = executor.submit(
            run_branch, "qwen3.5-4b", clone_graph(base_graph), qwen_input,
            args.clip_id, run_started, before_nodes, before_edges,
            args.work, args.qwen_max_attempts, args.qwen_max_new_tokens,
        )
        gemini_future = executor.submit(
            run_branch, "gemini-3.8-flash", clone_graph(base_graph), gemini_input,
            args.clip_id, run_started, before_nodes, before_edges,
            args.work, args.qwen_max_attempts, args.qwen_max_new_tokens,
        )
        branches = [qwen_future.result(), gemini_future.result()]
    for branch in branches:
        graph_object = branch.pop("graph_object")
        slug = branch["model"].replace(".", "_").replace("-", "_")
        save_graph(graph_object, args.results / f"{slug}_graph.pkl")
        write_json(args.results / f"{slug}.json", branch)
    (args.results / "comparison.md").write_text(markdown(shared, branches))
    print(json.dumps({
        "shared": shared,
        "branches": [{key: value for key, value in branch.items() if key in {
            "model", "transport", "vlm_ms", "text_embedding_ms", "graph_update_ms",
            "graph_insertion_ms", "equivalence_refresh_ms", "branch_ms",
            "end_to_end_memory_generation_ms", "tokens"
        }} for branch in branches],
    }, indent=2))


if __name__ == "__main__":
    main()
