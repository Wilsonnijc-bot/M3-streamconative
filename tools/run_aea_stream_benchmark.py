#!/usr/bin/env python3
"""Ingest ordered AEA RGB+audio into one M3 graph and evaluate at checkpoints."""

import argparse
import json
import os
import pickle
import re
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "StreamMeCo"
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)


def atomic_pickle(value, path):
    temporary = path.with_suffix(".tmp")
    with temporary.open("wb") as handle:
        pickle.dump(value, handle)
    temporary.replace(path)


def append(path, row):
    with path.open("a") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        handle.flush()


def segment(source, start, duration, target):
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-ss", f"{start:.3f}", "-i", str(source),
         "-t", f"{duration:.3f}", "-map", "0:v:0", "-map", "0:a:0",
         "-c:v", "libx264", "-preset", "ultrafast", "-crf", "18",
         "-c:a", "aac", "-ar", "16000", str(target)], check=True
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--segment-seconds", type=float, default=60)
    parser.add_argument("--max-segments", type=int, help="Limit ingestion for a smoke test")
    args = parser.parse_args()
    if args.segment_seconds <= 0:
        parser.error("--segment-seconds must be positive")
    dataset, results = args.dataset.resolve(), args.results.resolve()
    manifest = json.loads((dataset / "aea_6h_manifest.json").read_text())
    schedule = json.loads((dataset / "aea_6h_qa_schedule.json").read_text())
    entries = manifest["recordings"]
    if not entries or any(not e["audio_in_mp4"] for e in entries):
        raise ValueError("Dataset requires RGB MP4s with audio")
    for entry in entries:
        if not (dataset / entry["video_path"]).is_file():
            raise FileNotFoundError(dataset / entry["video_path"])
    checkpoints = defaultdict(list)
    for row in schedule["questions"]:
        checkpoints[row["ask_global_s"]].append(row)
    results.mkdir(parents=True, exist_ok=True)
    work = results / "work"
    (work / "intermediate").mkdir(parents=True, exist_ok=True)
    (results / "clip_audits").mkdir(exist_ok=True)
    from benchmarks import gemini_runtime as runtime
    from m3_agent.memorization_memory_graphs import process_segment
    from mmagent import retrieve
    from mmagent.utils.video_processing import process_video_clip
    from mmagent.videograph import VideoGraph
    config = json.loads((ROOT / "configs/memory_config.json").read_text())
    processing = json.loads((ROOT / "configs/processing_config.json").read_text())
    runtime.configure(results, "aea_stream")
    state_path = work / "state.pkl"
    if state_path.exists():
        with state_path.open("rb") as handle:
            state = pickle.load(handle)
        if state["manifest"] != manifest or state["schedule"] != schedule:
            raise ValueError("Refusing to resume with different source manifest or QA schedule")
        graph, completed, answered = state["graph"], set(state["completed"]), set(state["answered"])
        next_id = state["next_id"]
    else:
        graph, completed, answered, next_id = VideoGraph(**config), set(), set(), 1
    def save():
        atomic_pickle({"manifest": manifest, "schedule": schedule, "graph": graph,
                       "completed": sorted(completed), "answered": sorted(answered),
                       "next_id": next_id}, state_path)

    for entry in entries:
        source = dataset / entry["video_path"]
        duration = entry["duration_s"]
        boundaries = {0.0, duration}
        boundaries.update(min(duration, x * args.segment_seconds) for x in
                          range(1, int(duration / args.segment_seconds) + 1))
        boundaries.update(round(t - entry["global_start_s"], 3) for t in checkpoints
                          if entry["global_start_s"] < t < entry["global_end_s"])
        cuts = sorted(boundaries)
        for start, end in zip(cuts, cuts[1:]):
            if end - start < 0.01:
                continue
            key = f"{entry['sequence_id']}:{start:.3f}:{end:.3f}"
            if key not in completed:
                if args.max_segments and next_id > args.max_segments:
                    return
                temporary = work / f"active_{next_id}.mp4"
                try:
                    segment(source, start, end - start, temporary)
                    video, frames, audio = process_video_clip(
                        str(temporary), fps=processing["fps"], audio_duration_limit=end - start)
                    if not frames or not audio:
                        raise ValueError(f"Missing decoded RGB/audio at {key}")
                    runtime.CONTEXT.update(segment_id=next_id, question_id=None)
                    audit = process_segment(graph, video, frames, audio, next_id,
                                            {"intermediate_outputs": str(work / "intermediate"),
                                             "clip_audit_dir": str(results / "clip_audits"),
                                             "segment_end_s": entry["global_start_s"] + end},
                                            str(temporary))
                    append(results / "segments.jsonl", {"segment_id": next_id, "source": entry["sequence_id"],
                           "global_start_s": round(entry["global_start_s"] + start, 3),
                           "global_end_s": round(entry["global_start_s"] + end, 3),
                           "session_boundary": bool(start == 0 and entry["session_boundary"]),
                           "audit": audit})
                    completed.add(key)
                    next_id += 1
                    save()
                finally:
                    temporary.unlink(missing_ok=True)
            now = round(entry["global_start_s"] + end, 3)
            if now not in checkpoints:
                continue
            for qa in checkpoints[now]:
                if qa["question_id"] in answered:
                    continue
                assert qa["evidence_global_s"] < now
                runtime.CONTEXT.update(question_id=qa["question_id"], segment_id=None)
                retrieval_started = time.perf_counter()
                metrics = {}
                memories, _, _ = retrieve.search(
                    graph, qa["question"], [], topk=processing["topk"],
                    threshold=processing["retrieval_threshold"], metrics=metrics)
                retrieval_ms = (time.perf_counter() - retrieval_started) * 1000
                prompt = ("Answer this multiple-choice question using only the retrieved memories. "
                          "Return exactly one option letter (A, B, C, D, or E).\n\n"
                          f"Question: {qa['question']}\nOptions:\n" +
                          "\n".join(f"{chr(65 + i)}. {option}" for i, option in enumerate(qa["options"])) +
                          "\n\nRetrieved memories:\n" + json.dumps(memories, ensure_ascii=False))
                call = runtime.text_call("gemini", prompt, purpose="aea_qa")
                match = re.search(r"\b[A-E]\b", call["response"].upper())
                prediction = match.group(0) if match else None
                append(results / "answers.jsonl", {
                    "question_id": qa["question_id"], "current_global_s": now,
                    "source_video": qa["source_video"], "evidence_global_s": qa["evidence_global_s"],
                    "memory_lag_s": qa["memory_lag_s"], "retrieved_memories": memories,
                    "retrieval_metrics": metrics, "retrieval_latency_ms": retrieval_ms,
                    "answer_latency_ms": call["latency_ms"], "predicted_answer": prediction,
                    "ground_truth": qa["answer"], "correct": prediction == qa["answer"],
                })
                answered.add(qa["question_id"])
                save()
            print(f"CHECKPOINT {now:.0f}s questions={len(checkpoints[now])}", flush=True)
        print(f"COMPLETE {entry['sequence_id']}", flush=True)


if __name__ == "__main__":
    main()
