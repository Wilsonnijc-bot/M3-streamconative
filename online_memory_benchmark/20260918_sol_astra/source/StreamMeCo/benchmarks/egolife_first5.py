#!/usr/bin/env python3
"""Build one leak-free Jake Day 1 M3 stream and benchmark three retrieval modes."""
import argparse
import copy
import json
import os
import pickle
import re
import shutil
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

from m3_agent.memorization_memory_graphs import process_segment
from mmagent.prompts import prompt_answer_with_retrieval_final
from mmagent.retrieve import generate_action, search
from mmagent.utils.chat_qwen import generate_messages, get_response as qwen_response
from mmagent.utils.video_processing import process_video_clip
from mmagent.videograph import VideoGraph
from streammeco import compress_graph

MEMORY_CONFIG = json.loads((ROOT / "configs/memory_config.json").read_text())
PROCESSING_CONFIG = json.loads((ROOT / "configs/processing_config.json").read_text())
CHOICE_KEYS = ["choice_a", "choice_b", "choice_c", "choice_d"]
LETTERS = ["A", "B", "C", "D"]


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--clips", type=Path, required=True)
    parser.add_argument("--qa", type=Path, required=True)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--alpha", type=float, default=0.1)
    return parser.parse_args()


def atomic_pickle(value, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("wb") as handle:
        pickle.dump(value, handle)
    temp.replace(path)


def write_json(value, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temp.replace(path)


def append_jsonl(value, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(value, ensure_ascii=False) + "\n")
        handle.flush()


def clock_seconds(value):
    value = str(value).zfill(8)
    return int(value[:2]) * 3600 + int(value[2:4]) * 60 + int(value[4:6]) + int(value[6:]) / 100


def clip_clock(path):
    match = re.search(r"(\d{8})$", path.stem)
    if not match:
        raise ValueError(f"Cannot parse clip clock from {path.name}")
    return match.group(1)


def duration(path):
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(path)],
        check=True,
        capture_output=True,
        text=True,
    )
    return float(result.stdout.strip())


def clip_segment(source, start, end, target):
    if start <= 0.001 and end >= duration(source) - 0.02:
        return source
    target.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{start:.3f}",
            "-i", str(source), "-t", f"{max(0.01, end-start):.3f}", "-c:v", "libx264",
            "-preset", "ultrafast", "-crf", "18", "-c:a", "aac", "-ar", "16000", str(target),
        ],
        check=True,
    )
    return target


def public_question(qa):
    return {
        "id": str(qa["ID"]),
        "query_time": qa["query_time"],
        "question": qa["question"],
        "choices": {letter: qa[key] for letter, key in zip(LETTERS, CHOICE_KEYS)},
    }


def question_text(qa):
    choices = "\n".join(f"{letter}. {qa[key]}" for letter, key in zip(LETTERS, CHOICE_KEYS))
    return f"{qa['question']}\n{choices}"


def graph_counts(graph):
    counts = Counter(node.type for node in graph.nodes.values())
    return {
        "nodes": len(graph.nodes),
        "text_nodes": counts["episodic"] + counts["semantic"],
        "episodic_nodes": counts["episodic"],
        "semantic_nodes": counts["semantic"],
        "face_nodes": counts["img"],
        "voice_nodes": counts["voice"],
    }


def save_snapshot(graph, qa, index, segment_map, results):
    graph.refresh_equivalences()
    directory = results / "memory" / f"q{index}_uncompressed"
    directory.mkdir(parents=True, exist_ok=True)
    graph_path = directory / "graph.pkl"
    atomic_pickle(copy.deepcopy(graph), graph_path)
    metadata = {
        "question": public_question(qa),
        "graph": graph_counts(graph),
        "pickle_bytes": graph_path.stat().st_size,
        "last_segment_id": max(segment_map, default=0),
        "segment_map": segment_map,
    }
    write_json(metadata, directory / "metadata.json")


def load_first_five(path):
    rows = json.loads(path.read_text())
    rows = [row for row in rows if row.get("query_time", {}).get("date") == "DAY1"]
    rows.sort(key=lambda row: clock_seconds(row["query_time"]["time"]))
    return rows[:5]


def build_memory(args, questions):
    state_path = args.work / "build_state.pkl"
    if state_path.exists():
        with state_path.open("rb") as handle:
            state = pickle.load(handle)
        graph = state["graph"]
        completed = set(state["completed"])
        segment_map = state["segment_map"]
        next_segment = state["next_segment"]
    else:
        graph = VideoGraph(**MEMORY_CONFIG)
        completed, segment_map, next_segment = set(), {}, 1

    clips = sorted(
        [path for path in args.clips.iterdir() if path.suffix.lower() in {".mp4", ".mov", ".webm"}],
        key=lambda path: int(clip_clock(path)),
    )
    last_query_time = clock_seconds(questions[-1]["query_time"]["time"])
    for clip_position, source in enumerate(clips):
        source_clock = clip_clock(source)
        clip_start = clock_seconds(source_clock)
        if clip_start > last_query_time:
            break
        media_end = clip_start + duration(source)
        next_start = (
            clock_seconds(clip_clock(clips[clip_position + 1]))
            if clip_position + 1 < len(clips) else media_end
        )
        clip_end = min(media_end, next_start)
        boundaries = []
        for q_index, qa in enumerate(questions, 1):
            q_time = clock_seconds(qa["query_time"]["time"])
            if clip_start <= q_time < clip_end or (clip_position + 1 == len(clips) and q_time <= clip_end):
                boundaries.append((max(0.0, q_time - clip_start), q_index, qa))
        boundaries.sort()
        offset = 0.0
        for boundary, q_index, qa in boundaries:
            key = f"{source_clock}:{offset:.3f}:{boundary:.3f}"
            if boundary - offset >= 0.01 and key not in completed:
                target = args.work / "segments" / f"segment_{next_segment:04d}.mp4"
                actual = clip_segment(source, offset, boundary, target)
                clip_started = time.perf_counter()
                decode_started = time.perf_counter()
                base64_video, frames, audio = process_video_clip(
                    str(actual), fps=PROCESSING_CONFIG["fps"]
                )
                clip_metrics = {
                    "clip_decode_ms": (time.perf_counter() - decode_started) * 1000
                }
                if frames:
                    process_segment(
                        graph, base64_video, frames, audio, next_segment,
                        {
                            "intermediate_outputs": str(args.work / "intermediate"),
                            "clip_audit_dir": str(args.results / "clip_audits"),
                        },
                        str(actual),
                        metrics=clip_metrics,
                        total_started=clip_started,
                    )
                segment_map[next_segment] = {
                    "source": source.name, "source_clock": source_clock, "start_seconds": offset, "end_seconds": boundary,
                }
                completed.add(key)
                next_segment += 1
                atomic_pickle({"graph": graph, "completed": completed, "segment_map": segment_map, "next_segment": next_segment}, state_path)
                print(f"processed segment {next_segment - 1}: {source.name} [{offset:.2f}, {boundary:.2f}]", flush=True)
            snapshot = args.results / "memory" / f"q{q_index}_uncompressed" / "graph.pkl"
            if not snapshot.exists():
                save_snapshot(graph, qa, q_index, segment_map, args.results)
                print(f"saved q{q_index} snapshot at {qa['query_time']['time']}", flush=True)
            offset = boundary
            if q_index == len(questions):
                return
        if offset < clip_end - clip_start - 0.01:
            end = clip_end - clip_start
            key = f"{source_clock}:{offset:.3f}:{end:.3f}"
            if key not in completed:
                target = args.work / "segments" / f"segment_{next_segment:04d}.mp4"
                actual = clip_segment(source, offset, end, target)
                clip_started = time.perf_counter()
                decode_started = time.perf_counter()
                base64_video, frames, audio = process_video_clip(
                    str(actual), fps=PROCESSING_CONFIG["fps"]
                )
                clip_metrics = {
                    "clip_decode_ms": (time.perf_counter() - decode_started) * 1000
                }
                if frames:
                    process_segment(
                        graph, base64_video, frames, audio, next_segment,
                        {
                            "intermediate_outputs": str(args.work / "intermediate"),
                            "clip_audit_dir": str(args.results / "clip_audits"),
                        },
                        str(actual),
                        metrics=clip_metrics,
                        total_started=clip_started,
                    )
                segment_map[next_segment] = {"source": source.name, "source_clock": source_clock, "start_seconds": offset, "end_seconds": end}
                completed.add(key)
                next_segment += 1
                atomic_pickle({"graph": graph, "completed": completed, "segment_map": segment_map, "next_segment": next_segment}, state_path)
                print(f"processed segment {next_segment - 1}: {source.name} [{offset:.2f}, {end:.2f}]", flush=True)


def qwen_call(messages, enable_thinking=True):
    start = time.perf_counter()
    response, tokens = qwen_response(messages, enable_thinking=enable_thinking)
    return response, tokens, (time.perf_counter() - start) * 1000


def parse_prediction(text):
    matches = re.findall(r"(?:^|\b)([ABCD])(?:\b|[.)])", text.upper())
    return matches[-1] if matches else ""


def direct_answer(qa, memories):
    prompt = (
        "Answer this multiple-choice question using only the retrieved memories. "
        "Return exactly one letter: A, B, C, or D.\n\n"
        f"Question:\n{question_text(qa)}\n\nRetrieved memories:\n"
        + json.dumps(memories, ensure_ascii=False)
    )
    response, _, latency = qwen_call(generate_messages([{"type": "text", "content": prompt}]))
    return parse_prediction(response), response, latency


def one_shot(graph, qa):
    started = time.perf_counter()
    metrics = {}
    memories, _, scores = search(
        graph, qa["question"], [], topk=PROCESSING_CONFIG["topk"],
        threshold=PROCESSING_CONFIG["retrieval_threshold"], metrics=metrics,
    )
    prediction, raw, answer_ms = direct_answer(qa, memories)
    return {
        "retrieval_round_count": 1,
        "controller_call_count": 0,
        "retrieval_rounds": [metrics],
        "total_retrieval_ms": metrics["retrieval_round_total_ms"],
        "total_controller_ms": 0.0,
        "answer_model_ms": answer_ms,
        "full_question_answer_ms": (time.perf_counter() - started) * 1000,
        "retrieved_node_ids": metrics.get("returned_node_ids", []),
        "retrieval_scores": metrics.get("returned_node_scores", {}),
        "prediction": prediction,
        "raw_answer": raw,
    }


def normal_controller(graph, qa):
    started = time.perf_counter()
    context, responses, current_clips = [], [], []
    retrieval_rounds, controller_calls = [], []
    final_answer = ""
    switch = False
    for step in range(PROCESSING_CONFIG["max_retrieval_steps"]):
        call_start = time.perf_counter()
        reasoning, action_type, action_content = generate_action(
            question_text(qa), context, retrieval_plan=None,
            multiple_queries=False, responses=responses, switch=switch,
            model="qwen3.5-local",
        )
        latency = (time.perf_counter() - call_start) * 1000
        controller_calls.append({"purpose": "answer_or_search", "latency_ms": latency, "step": step + 1})
        responses.append({"reasoning": reasoning, "action_type": action_type, "action_content": action_content})
        if action_type == "answer":
            final_answer = action_content
            break
        if step == PROCESSING_CONFIG["max_retrieval_steps"] - 1:
            prompt = prompt_answer_with_retrieval_final.format(question=question_text(qa), information=context)
            raw, _, final_ms = qwen_call(generate_messages([{"type": "text", "content": prompt}]))
            controller_calls.append({"purpose": "forced_final_answer", "latency_ms": final_ms, "step": step + 1})
            final_answer = raw.split("[ANSWER]", 1)[-1].strip()
            break
        metrics = {}
        memories, current_clips, _ = search(
            graph, action_content, current_clips, topk=PROCESSING_CONFIG["topk"],
            threshold=PROCESSING_CONFIG["retrieval_threshold"], metrics=metrics,
        )
        retrieval_rounds.append(metrics)
        switch = not bool(memories) and PROCESSING_CONFIG.get("route_switch", True)
        context.append({"reasoning": reasoning, "query": action_content, "retrieved memories": memories})
    prediction = parse_prediction(final_answer)
    return {
        "retrieval_round_count": len(retrieval_rounds),
        "controller_call_count": len(controller_calls),
        "retrieval_rounds": retrieval_rounds,
        "controller_calls": controller_calls,
        "total_retrieval_ms": sum(row["retrieval_round_total_ms"] for row in retrieval_rounds),
        "total_controller_ms": sum(row["latency_ms"] for row in controller_calls),
        "answer_model_ms": controller_calls[-1]["latency_ms"] if controller_calls else 0.0,
        "full_question_answer_ms": (time.perf_counter() - started) * 1000,
        "prediction": prediction,
        "raw_answer": final_answer,
    }


def install_local_controller_adapter():
    import mmagent.retrieve as retrieve
    def local_retry(model, messages, timeout=30):
        response, tokens, _ = qwen_call(messages, enable_thinking=True)
        return response, tokens
    retrieve.get_response_with_retry = local_retry


def compress_snapshots(args, questions):
    metrics = []
    for index, qa in enumerate(questions, 1):
        source_dir = args.results / "memory" / f"q{index}_uncompressed"
        target_dir = args.results / "compressed_memory" / f"q{index}"
        target_dir.mkdir(parents=True, exist_ok=True)
        with (source_dir / "graph.pkl").open("rb") as handle:
            graph = pickle.load(handle)
        before = graph_counts(graph)
        before_bytes = (source_dir / "graph.pkl").stat().st_size
        started = time.perf_counter()
        compressed, summary = compress_graph(copy.deepcopy(graph), alpha=args.alpha)
        runtime_ms = (time.perf_counter() - started) * 1000
        target_path = target_dir / "graph.pkl"
        atomic_pickle(compressed, target_path)
        after = graph_counts(compressed)
        row = {
            "question_id": str(qa["ID"]), "snapshot": f"q{index}", "before": before, "after": after,
            "compression_ratio": after["nodes"] / before["nodes"] if before["nodes"] else 1.0,
            "memory_bytes_before": before_bytes, "memory_bytes_after": target_path.stat().st_size,
            "compression_runtime_ms": runtime_ms, "streammeco_summary": summary,
        }
        metrics.append(row)
        write_json(row, target_dir / "metadata.json")
    write_json(metrics, args.results / "compression_metrics.json")


def run_method(args, questions, method, output_name, compressed=False):
    output = args.results / output_name
    if output.exists():
        output.unlink()
    for index, qa in enumerate(questions, 1):
        graph_path = (
            args.results / "compressed_memory" / f"q{index}" / "graph.pkl"
            if compressed else args.results / "memory" / f"q{index}_uncompressed" / "graph.pkl"
        )
        with graph_path.open("rb") as handle:
            graph = pickle.load(handle)
        result = normal_controller(graph, qa) if method == "normal_controller" else one_shot(graph, qa)
        result.update({
            "question_index": index, "question": public_question(qa), "method": method,
            "memory": graph_counts(graph), "correct": result["prediction"] == qa["answer"],
        })
        append_jsonl(result, output)
        print(f"{method} q{index}: answer={result['prediction']} correct={result['correct']}", flush=True)
        for round_index, event in enumerate(result.get("retrieval_rounds", []), 1):
            append_jsonl({"question_index": index, "method": method, "event": "retrieval", "round": round_index, **event}, args.results / "detailed_latency_events.jsonl")
        for event in result.get("controller_calls", []):
            append_jsonl({"question_index": index, "method": method, "event": "controller", **event}, args.results / "detailed_latency_events.jsonl")


def load_jsonl(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_comparison(args):
    sources = [
        ("Normal controller", args.results / "retrieval_normal_controller.jsonl"),
        ("One-shot", args.results / "retrieval_oneshot.jsonl"),
        ("Compressed one-shot", args.results / "retrieval_compressed_oneshot.jsonl"),
    ]
    rows = []
    for label, path in sources:
        for item in load_jsonl(path):
            rounds = item["retrieval_rounds"]
            rows.append({
                "Q": f"Q{item['question_index']}", "Memory nodes": item["memory"]["nodes"], "Method": label,
                "Embed ms": sum(r.get("embedding_ms", 0) for r in rounds),
                "Search ms": sum(r.get("vector_search_ms", 0) for r in rounds),
                "StreamMeCo ms": sum(r.get("streammeco_tmr_scoring_ms", 0) + r.get("graph_node_selection_ms", 0) for r in rounds),
                "Retrieval total ms": item["total_retrieval_ms"], "Retrieval rounds": item["retrieval_round_count"],
                "Controller calls": item["controller_call_count"], "Answer-model ms": item["answer_model_ms"],
                "Full latency ms": item["full_question_answer_ms"], "Answer": item["prediction"], "Correct": item["correct"],
            })
    columns = list(rows[0])
    lines = ["# Jake Day 1: First Five Questions", "", "| " + " | ".join(columns) + " |", "| " + " | ".join("---:" if c.endswith("ms") or c in {"Memory nodes", "Retrieval rounds", "Controller calls"} else "---" for c in columns) + " |"]
    for row in rows:
        values = [f"{row[c]:.2f}" if isinstance(row[c], float) else str(row[c]) for c in columns]
        lines.append("| " + " | ".join(values) + " |")
    lines.extend(["", "## Averages", "", "| Method | Accuracy | Embed ms | Search ms | StreamMeCo ms | Retrieval total ms | Retrieval rounds | Controller calls | Answer-model ms | Full latency ms |", "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"])
    for label, _ in sources:
        selected = [row for row in rows if row["Method"] == label]
        mean = lambda key: sum(float(row[key]) for row in selected) / len(selected)
        accuracy = sum(bool(row["Correct"]) for row in selected) / len(selected)
        lines.append(f"| {label} | {accuracy:.3f} | {mean('Embed ms'):.2f} | {mean('Search ms'):.2f} | {mean('StreamMeCo ms'):.2f} | {mean('Retrieval total ms'):.2f} | {mean('Retrieval rounds'):.2f} | {mean('Controller calls'):.2f} | {mean('Answer-model ms'):.2f} | {mean('Full latency ms'):.2f} |")
    (args.results / "comparison.md").write_text("\n".join(lines) + "\n")


def main():
    args = parse_args()
    args.results.mkdir(parents=True, exist_ok=True)
    args.work.mkdir(parents=True, exist_ok=True)
    questions = load_first_five(args.qa)
    write_json([public_question(row) for row in questions], args.results / "questions_without_gold.json")
    build_memory(args, questions)
    compress_snapshots(args, questions)
    latency_path = args.results / "detailed_latency_events.jsonl"
    if latency_path.exists():
        latency_path.unlink()
    install_local_controller_adapter()
    run_method(args, questions, "normal_controller", "retrieval_normal_controller.jsonl")
    run_method(args, questions, "oneshot", "retrieval_oneshot.jsonl")
    run_method(args, questions, "compressed_oneshot", "retrieval_compressed_oneshot.jsonl", compressed=True)
    write_comparison(args)
    write_json({"status": "complete", "completed_at": time.strftime("%Y-%m-%dT%H:%M:%S%z")}, args.results / "run_status.json")
    print("BENCHMARK_COMPLETE", flush=True)


if __name__ == "__main__":
    main()
