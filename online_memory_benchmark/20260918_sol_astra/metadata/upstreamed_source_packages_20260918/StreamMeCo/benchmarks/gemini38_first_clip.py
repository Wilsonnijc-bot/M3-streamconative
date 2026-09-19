#!/usr/bin/env python3
"""Generate a fully audited Gemini memory update for one video clip."""
import argparse
import json
import os
import pickle
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

from mmagent.clip_audit import graph_delta, graph_identity, graph_view, write_json
from mmagent.face_processing import process_faces
from mmagent.memory_processing_qwen import generate_video_context, process_memories
from mmagent.prompts import prompt_generate_memory_with_ids_sft
from mmagent.utils.chat_gemini import MODEL, generate_messages, get_response
from mmagent.utils.general import validate_and_fix_json
from mmagent.utils.video_processing import process_video_clip
from mmagent.videograph import VideoGraph
from mmagent.voice_processing import process_voices


MEMORY_CONFIG = json.loads((ROOT / "configs/memory_config.json").read_text())
PROCESSING_CONFIG = json.loads((ROOT / "configs/processing_config.json").read_text())


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--clip", type=Path, required=True)
    parser.add_argument("--clip-id", type=int, default=1)
    parser.add_argument("--faces", type=Path, required=True)
    parser.add_argument("--voices", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--request-output", type=Path)
    parser.add_argument("--response-input", type=Path)
    parser.add_argument("--graph-input", type=Path)
    parser.add_argument("--graph-output", type=Path)
    parser.add_argument("--memory-override", type=Path)
    parser.add_argument("--fresh-intermediates", action="store_true")
    parser.add_argument("--fps", type=float, default=2.0)
    parser.add_argument("--max-pixels", type=int, default=151200)
    return parser.parse_args()


def load_graph(path):
    if path and path.exists():
        with path.open("rb") as handle:
            return pickle.load(handle)
    return VideoGraph(**MEMORY_CONFIG)


def save_graph(graph, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("wb") as handle:
        pickle.dump(graph, handle)
    temp.replace(path)


def load_override(path):
    if not path.exists():
        write_json(path, {
            "video_description": None,
            "high_level_conclusions": None,
        })
    value = json.loads(path.read_text())
    for key in ("video_description", "high_level_conclusions"):
        replacement = value.get(key)
        if replacement is not None and (
            not isinstance(replacement, list)
            or not all(isinstance(item, str) for item in replacement)
        ):
            raise ValueError(f"{path}: {key} must be null or a list of strings")
    return value


def prepare(args):
    if args.fresh_intermediates:
        args.faces.unlink(missing_ok=True)
        args.voices.unlink(missing_ok=True)
    started_epoch = time.time()
    total_started = time.perf_counter()
    graph = load_graph(args.graph_input)
    before_nodes, before_edges = graph_identity(graph)

    decode_started = time.perf_counter()
    base64_video, frames, audio = process_video_clip(
        str(args.clip), fps=PROCESSING_CONFIG["fps"]
    )
    decode_ms = (time.perf_counter() - decode_started) * 1000

    voice_metrics = {}
    voices = process_voices(
        graph,
        audio,
        base64_video,
        save_path=str(args.voices),
        preprocessing=[],
        metrics=voice_metrics,
    )
    face_metrics = {}
    faces = process_faces(
        graph,
        frames,
        save_path=str(args.faces),
        preprocessing=[],
        metrics=face_metrics,
    )

    context_started = time.perf_counter()
    video_context = generate_video_context(
        frames, faces, voices, video_path=str(args.clip)
    )
    messages, media = generate_messages(
        [{"type": "text", "content": prompt_generate_memory_with_ids_sft}]
        + video_context,
        fps=args.fps,
        max_pixels=args.max_pixels,
    )
    context_ms = (time.perf_counter() - context_started) * 1000
    request = {
        "model": MODEL,
        "messages": messages,
        "temperature": PROCESSING_CONFIG["temperature"],
        "max_tokens": 8192,
    }
    state_path = (
        args.request_output.with_suffix(".graph.pkl")
        if args.request_output else args.output.with_suffix(".pre_vlm_graph.pkl")
    )
    save_graph(graph, state_path)
    metadata = {
        "started_epoch": started_epoch,
        "pre_vlm_elapsed_ms": (time.perf_counter() - total_started) * 1000,
        "state_path": str(state_path),
        "before_nodes": sorted(before_nodes),
        "before_edges": [list(edge) for edge in sorted(before_edges)],
        "latency_ms": {
            "clip_decode": decode_ms,
            "context_preparation": context_ms,
        },
        "stage_details": {"voice": voice_metrics, "face": face_metrics},
        "media": media,
        "counts": {
            "input_frames_for_preprocessing": len(frames),
            "voice_identities": len(voices),
            "face_identities": len(faces),
        },
    }
    return graph, request, metadata


def load_prepared(args):
    handoff = json.loads(args.request_output.read_text())
    metadata = handoff["metadata"]
    graph = load_graph(Path(metadata["state_path"]))
    return graph, handoff["request"], metadata


def main():
    args = parse_args()
    if args.response_input and args.request_output and args.request_output.exists():
        graph, request, metadata = load_prepared(args)
    else:
        graph, request, metadata = prepare(args)

    if args.request_output and not args.response_input:
        args.request_output.parent.mkdir(parents=True, exist_ok=True)
        args.request_output.write_text(json.dumps({
            "request": request,
            "metadata": metadata,
        }) + "\n")
        print(json.dumps({
            "request_output": str(args.request_output),
            **metadata["latency_ms"],
            **metadata["media"],
            **metadata["counts"],
        }, indent=2))
        return

    call_started = time.perf_counter()
    if args.response_input:
        response = json.loads(args.response_input.read_text())
        raw = response["choices"][0]["message"].get("content") or ""
        tokens = (response.get("usage") or {}).get("total_tokens")
        vlm_ms = float(response.get("_client_latency_seconds", 0.0)) * 1000
    else:
        raw, tokens = get_response(request["messages"])
        response = {}
        vlm_ms = (time.perf_counter() - call_started) * 1000

    parsed = validate_and_fix_json(raw)
    if not isinstance(parsed, dict):
        raise ValueError("Gemini did not return a valid memory object")
    generated_memory = {
        "video_description": list(parsed.get(
            "video_descriptions", parsed.get("video_description", [])
        )),
        "high_level_conclusions": list(parsed.get("high_level_conclusions", [])),
    }
    override_path = args.memory_override or args.output.with_name(
        f"clip_{args.clip_id}_memory_override.json"
    )
    override = load_override(override_path)
    effective_memory = {
        key: list(value) for key, value in generated_memory.items()
    }
    override_applied = {}
    for key in effective_memory:
        replacement = override.get(key)
        override_applied[key] = replacement is not None
        if replacement is not None:
            effective_memory[key] = replacement

    embedding_bundle = response.get("_memory_embeddings") or {}
    embedding_texts = response.get("_embedding_texts") or {}
    embedding_ms = response.get("_text_embedding_latency_ms") or {}

    def handoff_embeddings(key, texts):
        values = embedding_bundle.get(key)
        if values is None:
            return None, None
        if embedding_texts.get(key) != texts:
            raise ValueError(
                f"Precomputed embeddings for {key} do not match effective memory text"
            )
        return values, embedding_ms.get(key)

    episodic_embeddings, episodic_embedding_ms = handoff_embeddings(
        "video_description", effective_memory["video_description"]
    )
    semantic_embeddings, semantic_embedding_ms = handoff_embeddings(
        "high_level_conclusions", effective_memory["high_level_conclusions"]
    )
    episodic_metrics = {}
    semantic_metrics = {}
    process_memories(
        graph,
        effective_memory["video_description"],
        args.clip_id,
        type="episodic",
        metrics=episodic_metrics,
        precomputed_embeddings=episodic_embeddings,
        precomputed_embedding_ms=episodic_embedding_ms,
    )
    process_memories(
        graph,
        effective_memory["high_level_conclusions"],
        args.clip_id,
        type="semantic",
        metrics=semantic_metrics,
        precomputed_embeddings=semantic_embeddings,
        precomputed_embedding_ms=semantic_embedding_ms,
    )

    before_nodes = set(metadata["before_nodes"])
    before_edges = {tuple(edge) for edge in metadata["before_edges"]}
    readable_graph = graph_view(graph)
    delta = graph_delta(graph, before_nodes, before_edges)
    graph_output = args.graph_output or args.output.with_name(
        f"clip_{args.clip_id}_graph.pkl"
    )
    graph_json = graph_output.with_suffix(".json")
    save_graph(graph, graph_output)
    write_json(graph_json, readable_graph)

    voice = metadata["stage_details"]["voice"]
    face = metadata["stage_details"]["face"]
    text_embedding_ms = (
        episodic_metrics["text_embedding_ms"]
        + semantic_metrics["text_embedding_ms"]
    )
    graph_update_ms = sum(
        value or 0.0 for value in (
            voice.get("graph_update_ms"),
            face.get("graph_update_ms"),
            episodic_metrics.get("graph_update_ms"),
            semantic_metrics.get("graph_update_ms"),
        )
    )
    stage_sum_ms = sum(
        value or 0.0 for value in (
            metadata["latency_ms"]["clip_decode"],
            voice.get("total_ms"),
            face.get("total_ms"),
            metadata["latency_ms"]["context_preparation"],
            vlm_ms,
            episodic_metrics.get("text_embedding_ms"),
            episodic_metrics.get("graph_update_ms"),
            semantic_metrics.get("text_embedding_ms"),
            semantic_metrics.get("graph_update_ms"),
        )
    )
    audit = {
        "model": MODEL,
        "clip_id": args.clip_id,
        "asr_selected_provider": voice.get("asr_selected_provider"),
        "clip": str(args.clip),
        "end_to_end_memory_generation_ms": (
            time.time() - metadata["started_epoch"]
        ) * 1000,
        "pipeline_stage_sum_ms": stage_sum_ms,
        "handoff_used": bool(args.response_input),
        "latency_ms": {
            "clip_decode": metadata["latency_ms"]["clip_decode"],
            "deepgram_asr": voice.get("asr_provider_ms", {}).get("deepgram-asr"),
            "mai_transcribe_asr": voice.get("asr_provider_ms", {}).get("openrouter-mai-transcribe-2"),
            "asr_total": voice.get("asr_total_ms"),
            "audio_segmentation": voice.get("audio_segmentation_ms"),
            "speech_embedding_campplus": voice.get("speech_embedding_ms"),
            "facial_detection_recognition_buffalo_l": face.get("face_detection_recognition_ms"),
            "face_clustering": face.get("face_clustering_ms"),
            "context_preparation": metadata["latency_ms"]["context_preparation"],
            "vlm_memory_generation": vlm_ms,
            "text_embedding": text_embedding_ms,
            "graph_update_total": graph_update_ms,
        },
        "stage_details": {
            **metadata["stage_details"],
            "episodic_memory": episodic_metrics,
            "semantic_memory": semantic_metrics,
        },
        "counts": {
            **metadata["counts"],
            **metadata["media"],
            "episodic_memories": len(effective_memory["video_description"]),
            "semantic_memories": len(effective_memory["high_level_conclusions"]),
            "nodes_after_clip": readable_graph["counts"]["nodes"],
            "edges_after_clip": readable_graph["counts"]["edges"],
            "nodes_added_by_clip": delta["nodes_added"],
            "edges_added_by_clip": delta["edges_added"],
        },
        "usage": response.get("usage"),
        "total_tokens": tokens,
        "raw_gemini_response": raw,
        "generated_memory": generated_memory,
        "effective_memory": effective_memory,
        "override": {
            "path": str(override_path),
            "applied": override_applied,
        },
        "graph_delta": delta,
        "artifacts": {
            "readable_graph_json": str(graph_json),
            "exact_graph_pickle": str(graph_output),
        },
    }
    write_json(args.output, audit)
    print(json.dumps({
        "output": str(args.output),
        "end_to_end_memory_generation_ms": audit["end_to_end_memory_generation_ms"],
        "pipeline_stage_sum_ms": audit["pipeline_stage_sum_ms"],
        "latency_ms": audit["latency_ms"],
        "counts": audit["counts"],
        "valid_memory_json": True,
    }, indent=2))


if __name__ == "__main__":
    main()
