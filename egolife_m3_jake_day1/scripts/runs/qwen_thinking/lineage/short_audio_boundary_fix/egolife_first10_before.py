#!/usr/bin/env python3
"""Build one Jake Day 1 M3 stream and benchmark StreamMeCo retrieval variants."""

from __future__ import annotations

import argparse
import copy
import json
import os
import pickle
import re
import subprocess
import sys
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from statistics import mean, median

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

os.environ.pop("EGOLIFE_GEMINI_ONLY", None)
os.environ["EGOLIFE_QWEN_ONLY"] = "1"
from benchmarks import qwen_runtime as runtime
import httpx

from m3_agent.export_mandol import export_graph
from m3_agent.memorization_memory_graphs import process_segment
from mmagent import retrieve
from mmagent.clip_audit import graph_view
from mmagent.prompts import (
    prompt_answer_with_retrieval_final,
    prompt_generate_action_with_plan,
    prompt_generate_action_with_plan_new_direction,
)
from mmagent.utils import chat_api
from mmagent.utils.video_processing import process_video_clip
from mmagent.videograph import VideoGraph
from streammeco import compress_graph

MEMORY_CONFIG = json.loads((ROOT / "configs/memory_config.json").read_text())
PROCESSING_CONFIG = json.loads((ROOT / "configs/processing_config.json").read_text())
CHOICE_KEYS = ["choice_a", "choice_b", "choice_c", "choice_d"]
LETTERS = ["A", "B", "C", "D"]
OUTPUT_NAMES = {
    ("A", "qwen"): "method_A_normal_streammeco.jsonl",
    ("B", "qwen"): "method_B_streammeco_oneshot.jsonl",
    ("C", "qwen"): "method_C_compressed_oneshot.jsonl",
}

_embedding_events: list[dict] | None = None
_embedding_lock = threading.Lock()


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "phase",
        choices=["build", "compress", "export-mandol", "eval", "report", "validate"],
    )
    parser.add_argument("--clips", type=Path)
    parser.add_argument("--qa", type=Path, required=True)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--method", choices=["A", "B", "C"])
    parser.add_argument("--backend", choices=["qwen"], default="qwen")
    parser.add_argument("--alpha", type=float, default=0.1)
    parser.add_argument("--qwen-url", default="http://127.0.0.1:8765/generate")
    parser.add_argument("--top-k", type=int, default=PROCESSING_CONFIG["topk"])
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--max-segments", type=int)
    parser.add_argument("--prefetch", type=int, choices=[0,2,4], default=2)
    return parser.parse_args()


def atomic_pickle(value, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("wb") as handle:
        pickle.dump(value, handle)
    temporary.replace(path)


def write_json(value, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def append_jsonl(value, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(value, ensure_ascii=False) + "\n")
        handle.flush()


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def clock_seconds(value) -> float:
    value = str(value).zfill(8)
    return (
        int(value[:2]) * 3600
        + int(value[2:4]) * 60
        + int(value[4:6])
        + int(value[6:]) / 100
    )


def clip_clock(path: Path) -> str:
    match = re.search(r"(\d{8})$", path.stem)
    if not match:
        raise ValueError(f"Cannot parse clip clock from {path.name}")
    return match.group(1)


def media_duration(path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=nw=1:nk=1",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return float(result.stdout.strip())


def clip_segment(source: Path, start: float, end: float, target: Path) -> Path:
    source_duration = media_duration(source)
    if start <= 0.001 and end >= source_duration - 0.02:
        return source
    target.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-ss",
            f"{start:.3f}",
            "-i",
            str(source),
            "-t",
            f"{max(0.01, end - start):.3f}",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-crf",
            "18",
            "-c:a",
            "aac",
            "-ar",
            "16000",
            str(target),
        ],
        check=True,
    )
    return target


def public_question(qa: dict) -> dict:
    return {
        "id": str(qa["ID"]),
        "query_time": qa["query_time"],
        "question": qa["question"],
        "choices": {letter: qa[key] for letter, key in zip(LETTERS, CHOICE_KEYS)},
    }


def question_text(question: dict) -> str:
    choices = "\n".join(
        f"{letter}. {question['choices'][letter]}" for letter in LETTERS
    )
    return f"{question['question']}\n{choices}"


def load_questions(path: Path) -> tuple[list[dict], list[dict]]:
    rows = json.loads(path.read_text())
    rows = [row for row in rows if row.get("query_time", {}).get("date") == "DAY1"]
    rows.sort(key=lambda row: clock_seconds(row["query_time"]["time"]))
    selected = rows[:10]
    if len(selected) != 10:
        raise ValueError(f"Expected 10 DAY1 questions, found {len(selected)}")
    return selected, [public_question(row) for row in selected]


def graph_counts(graph) -> dict:
    counts = Counter(node.type for node in graph.nodes.values())
    return {
        "nodes": len(graph.nodes),
        "edges": len(graph.edges) // 2,
        "episodic_nodes": counts["episodic"],
        "semantic_nodes": counts["semantic"],
        "face_nodes": counts["img"],
        "voice_nodes": counts["voice"],
        "node_type_counts": dict(sorted(counts.items())),
    }


def _write_graph_artifacts(graph, directory: Path):
    readable = graph_view(graph)
    write_json(readable, directory / "graph.json")
    with (directory / "nodes.jsonl").open("w", encoding="utf-8") as handle:
        for node in readable["nodes"]:
            handle.write(json.dumps(node, ensure_ascii=False) + "\n")
    with (directory / "edges.jsonl").open("w", encoding="utf-8") as handle:
        for edge in readable["edges"]:
            handle.write(json.dumps(edge, ensure_ascii=False) + "\n")


def save_snapshot(graph, qa: dict, index: int, segment_map: dict, results: Path):
    snapshot = copy.deepcopy(graph)
    snapshot.refresh_equivalences()
    directory = results / "memory" / f"q{index:02d}_uncompressed"
    directory.mkdir(parents=True, exist_ok=True)
    graph_path = directory / "graph.pkl"
    atomic_pickle(snapshot, graph_path)
    _write_graph_artifacts(snapshot, directory)
    query_seconds = clock_seconds(qa["query_time"]["time"])
    segments = [segment_map[key] for key in sorted(segment_map)]
    leakage = [row for row in segments if row["absolute_end_seconds"] > query_seconds + 1e-6]
    if leakage:
        raise RuntimeError(f"Future leakage detected for q{index:02d}: {leakage[:1]}")
    metadata = {
        "question": public_question(qa),
        "query_time_seconds": query_seconds,
        "graph": graph_counts(snapshot),
        "native_graph": "graph.pkl",
        "readable_graph": "graph.json",
        "pickle_bytes": graph_path.stat().st_size,
        "last_segment_id": max(segment_map, default=0),
        "source_segments": segments,
        "future_leakage": False,
        "asr_degraded_segments": [row for row in segments if row.get("asr_failures")],
        "skipped_segments": [row for row in segments if row.get("status") == "skipped_api_failure"],
    }
    write_json(metadata, directory / "metadata.json")
    write_json(segments, directory / "source_clips.json")


def _process_one_segment(
    graph,
    actual: Path,
    segment_id: int,
    source: Path,
    source_clock: str,
    offset: float,
    end: float,
    args,
) -> dict:
    if args.max_segments and segment_id > args.max_segments:
        raise SystemExit(0)
    clip_started = time.perf_counter()
    prepared = getattr(args, '_current_prepared', None)
    if prepared:
        base64_video, frames, audio = prepared['decoded']
        metrics = {'clip_decode_ms':prepared['decode_ms']}
    else:
        decode_started = time.perf_counter()
        base64_video, frames, audio = process_video_clip(str(actual), fps=PROCESSING_CONFIG['fps'])
        metrics = {'clip_decode_ms':(time.perf_counter()-decode_started)*1000}
    if frames:
        runtime.CONTEXT.update(segment_id=segment_id, question_id=None, method=None)
        audit = process_segment(
            graph,
            base64_video,
            frames,
            audio,
            segment_id,
            {
                "intermediate_outputs": str(args.work / "intermediate"),
                "clip_audit_dir": str(args.results / "clip_audits"),
                "prepared_asr": prepared.get("asr") if prepared else None,
            },
            str(actual),
            metrics=metrics,
            total_started=clip_started,
        )
        audit["memory_pickle_bytes"] = Path(audit["artifacts"]["exact_graph_pickle"]).stat().st_size
        audit["reasoning_model"] = runtime.MODEL
        audit["execution_policy"] = "concurrent_asr_pooled_http_clip_embedding_batch_prefetch"
        if prepared:
            audit["pipeline_timing"] = prepared["pipeline_timing"]
            audit["ordered_processing_ms"] = audit["end_to_end_memory_generation_ms"]
            audit["end_to_end_memory_generation_ms"] = (time.perf_counter()-prepared["pipeline_timing"]["admitted_perf"])*1000
        write_json(audit, args.results / "clip_audits" / f"clip_{segment_id}_audit.json")
        append_jsonl(audit, args.results / "memory_construction_latency.jsonl")
    else:
        raise RuntimeError(f"No frames decoded: {actual}")
    absolute_start = clock_seconds(source_clock) + offset
    absolute_end = clock_seconds(source_clock) + end
    return {
        "segment_id": segment_id,
        "source": source.name,
        "source_clock": source_clock,
        "start_seconds_in_source": offset,
        "end_seconds_in_source": end,
        "absolute_start_seconds": absolute_start,
        "absolute_end_seconds": absolute_end,
        "actual_media": str(actual),
        "asr_failures": audit["stage_details"]["voice"].get("asr_failures", []),
    }


def process_one_segment(graph, actual, segment_id, source, source_clock, offset, end, args):
    from benchmarks.segment_resilience import transactional_segment
    if args.max_segments and segment_id > args.max_segments:
        raise SystemExit(0)
    if getattr(args, '_prefetcher', None):
        args._current_prepared = args._prefetcher.get(segment_id)
        prepared = args._current_prepared
        if prepared['source_name'] != source.name or abs(prepared['offset']-offset) > .001 or abs(prepared['end']-end) > .001:
            raise RuntimeError('Prefetch chronology does not match ordered segment plan')
        actual = prepared['actual']
    metadata = {
        'segment_id':segment_id,'source':source.name,'source_clock':source_clock,
        'start_seconds_in_source':offset,'end_seconds_in_source':end,
        'absolute_start_seconds':clock_seconds(source_clock)+offset,
        'absolute_end_seconds':clock_seconds(source_clock)+end,'actual_media':str(actual),
    }
    result = transactional_segment(
        graph, lambda: _process_one_segment(graph, actual, segment_id, source, source_clock, offset, end, args),
        metadata, args.results,
    )
    if getattr(args, "_current_prepared", None):
        result["pipeline_timing"] = args._current_prepared["pipeline_timing"]
    return result


def record_segment_commit(row, results):
    event={'segment_id':row['segment_id'],'status':row.get('status','committed'),'commit_epoch':time.time()}
    timing=row.get('pipeline_timing')
    if timing:
        now=time.perf_counter()
        event.update(timing,commit_perf=now,segment_latency_ms=(now-timing['admitted_perf'])*1000,
                     ordered_stage_ms=(now-timing['ordered_start_perf'])*1000)
    append_jsonl(event,results/'segment_schedule_events.jsonl')


def build_memory(args, questions: list[dict]):
    if args.clips is None:
        raise ValueError("--clips is required for build")
    state_path = args.work / "build_state.pkl"
    if state_path.exists():
        with state_path.open("rb") as handle:
            state = pickle.load(handle)
        if state.get("reasoning_model") != runtime.MODEL:
            raise RuntimeError("Refusing to resume incompatible Qwen memory")
        graph = state["graph"]
        completed = set(state["completed"])
        segment_map = state["segment_map"]
        next_segment = state["next_segment"]
        print(f"RESUME_BUILD completed_segments={len(completed)}", flush=True)
    else:
        graph = VideoGraph(**MEMORY_CONFIG)
        completed, segment_map, next_segment = set(), {}, 1

    clips = sorted(
        [
            path
            for path in args.clips.iterdir()
            if path.suffix.lower() in {".mp4", ".mov", ".webm"}
        ],
        key=lambda path: int(clip_clock(path)),
    )
    if not clips:
        raise FileNotFoundError(f"No clips found in {args.clips}")
    if args.prefetch:
        from benchmarks.segment_prefetch import SegmentPrefetch
        from mmagent.utils.asr_resilience import concurrent_providers
        import base64
        plan = []
        last = clock_seconds(questions[-1]['query_time']['time'])
        for pos, src in enumerate(clips):
            start = clock_seconds(clip_clock(src))
            if start > last: break
            end = min(start+media_duration(src), clock_seconds(clip_clock(clips[pos+1])) if pos+1<len(clips) else float('inf'),last)
            cuts = sorted({clock_seconds(q['query_time']['time']) for q in questions if start < clock_seconds(q['query_time']['time']) < end}) + [end]
            offset = 0.0
            for boundary in cuts:
                finish = boundary-start
                if finish-offset >= .01: plan.append((src,offset,finish))
                offset=finish
            if end==last: break
        write_json({'segments':len(plan),'source_clips':len({str(r[0]) for r in plan}),'plan':[{'source':str(r[0]),'start':r[1],'end':r[2]} for r in plan]},args.results/'segment_plan.json')
        if args.max_segments: plan=plan[:args.max_segments]
        def prepare(row, segment_id):
            src, offset, end = row
            actual = clip_segment(src,offset,end,args.work/'segments'/f'segment_{segment_id:04d}.mp4')
            started=time.perf_counter()
            decoded=process_video_clip(str(actual),fps=PROCESSING_CONFIG['fps'])
            result={'actual':actual,'decoded':decoded,'decode_ms':(time.perf_counter()-started)*1000,'source_name':src.name,'offset':offset,'end':end}
            if decoded[2] and not (args.work/'intermediate'/f'clip_{segment_id}_voices.json').exists():
                audio=base64.b64decode(decoded[2])
                result['asr']=concurrent_providers(PROCESSING_CONFIG['asr_providers'],
                    lambda provider: chat_api.transcribe_audio_with_retry(provider,audio,audio_format='wav',context={'segment_id':segment_id,'phase':'preparation'}))
            return result
        args._prefetcher=SegmentPrefetch(plan,prepare,args.prefetch)
        print(f'PREPARATION_LOOKAHEAD={args.prefetch} planned_segments={len(plan)}',flush=True)
    last_query_time = clock_seconds(questions[-1]["query_time"]["time"])
    for position, source in enumerate(clips):
        source_clock = clip_clock(source)
        clip_start = clock_seconds(source_clock)
        if clip_start > last_query_time:
            break
        source_duration = media_duration(source)
        media_end = clip_start + source_duration
        next_start = (
            clock_seconds(clip_clock(clips[position + 1]))
            if position + 1 < len(clips)
            else media_end
        )
        clip_end = min(media_end, next_start)
        boundaries = []
        for q_index, qa in enumerate(questions, 1):
            q_time = clock_seconds(qa["query_time"]["time"])
            if clip_start <= q_time < clip_end or (
                position + 1 == len(clips) and q_time <= clip_end
            ):
                boundaries.append((max(0.0, q_time - clip_start), q_index, qa))
        boundaries.sort()
        offset = 0.0
        for boundary, q_index, qa in boundaries:
            key = f"{source_clock}:{offset:.3f}:{boundary:.3f}"
            if boundary - offset >= 0.01 and key not in completed:
                target = args.work / "segments" / f"segment_{next_segment:04d}.mp4"
                actual = source if args.prefetch else clip_segment(source, offset, boundary, target)
                segment_map[next_segment] = process_one_segment(
                    graph,
                    actual,
                    next_segment,
                    source,
                    source_clock,
                    offset,
                    boundary,
                    args,
                )
                completed.add(key)
                next_segment += 1
                atomic_pickle(
                    {
                        "graph": graph,
                        "reasoning_model": runtime.MODEL,
                        "completed": completed,
                        "segment_map": segment_map,
                        "next_segment": next_segment,
                    },
                    state_path,
                )
                record_segment_commit(segment_map[next_segment - 1], args.results)
                print(
                    f"SEGMENT_{'SKIPPED' if segment_map[next_segment - 1].get('status') == 'skipped_api_failure' else 'COMPLETE'} id={next_segment - 1} source={source.name} "
                    f"range={offset:.2f}:{boundary:.2f}",
                    flush=True,
                )
            snapshot = args.results / "memory" / f"q{q_index:02d}_uncompressed" / "graph.pkl"
            if not snapshot.exists():
                save_snapshot(graph, qa, q_index, segment_map, args.results)
                print(
                    f"SNAPSHOT_COMPLETE q={q_index:02d} time={qa['query_time']['time']}",
                    flush=True,
                )
            offset = boundary
            if q_index == len(questions):
                write_json(
                    {
                        "status": "complete",
                        "segments": len(segment_map),
                        "committed_segments": sum(s.get("status", "committed") == "committed" for s in segment_map.values()),
                        "skipped_segments": sum(s.get("status") == "skipped_api_failure" for s in segment_map.values()),
                        "completed_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                    },
                    args.results / "memory_build_status.json",
                )
                print("MEMORY_BUILD_COMPLETE", flush=True)
                return
        end = clip_end - clip_start
        if offset < end - 0.01:
            key = f"{source_clock}:{offset:.3f}:{end:.3f}"
            if key not in completed:
                target = args.work / "segments" / f"segment_{next_segment:04d}.mp4"
                actual = source if args.prefetch else clip_segment(source, offset, end, target)
                segment_map[next_segment] = process_one_segment(
                    graph,
                    actual,
                    next_segment,
                    source,
                    source_clock,
                    offset,
                    end,
                    args,
                )
                completed.add(key)
                next_segment += 1
                atomic_pickle(
                    {
                        "graph": graph,
                        "reasoning_model": runtime.MODEL,
                        "completed": completed,
                        "segment_map": segment_map,
                        "next_segment": next_segment,
                    },
                    state_path,
                )
                record_segment_commit(segment_map[next_segment - 1], args.results)
                print(
                    f"SEGMENT_{'SKIPPED' if segment_map[next_segment - 1].get('status') == 'skipped_api_failure' else 'COMPLETE'} id={next_segment - 1} source={source.name} "
                    f"range={offset:.2f}:{end:.2f}",
                    flush=True,
                )
    raise RuntimeError("Reached end of clips before the tenth query timestamp")


def compress_snapshots(args, questions: list[dict]):
    metrics = []
    for index, qa in enumerate(questions, 1):
        source_dir = args.results / "memory" / f"q{index:02d}_uncompressed"
        target_dir = args.results / "streammeco_compressed" / f"q{index:02d}"
        if (target_dir / "graph.pkl").exists():
            metrics.append(json.loads((target_dir / "metadata.json").read_text()))
            continue
        target_dir.mkdir(parents=True, exist_ok=True)
        with (source_dir / "graph.pkl").open("rb") as handle:
            graph = pickle.load(handle)
        before = graph_counts(graph)
        before_bytes = (source_dir / "graph.pkl").stat().st_size
        started = time.perf_counter()
        compressed, summary = compress_graph(copy.deepcopy(graph), alpha=args.alpha)
        latency_ms = (time.perf_counter() - started) * 1000
        target_path = target_dir / "graph.pkl"
        atomic_pickle(compressed, target_path)
        _write_graph_artifacts(compressed, target_dir)
        after = graph_counts(compressed)
        row = {
            "question_id": str(qa["ID"]),
            "snapshot": f"q{index:02d}",
            "source_graph_sha256": __import__("hashlib").sha256((source_dir / "graph.pkl").read_bytes()).hexdigest(),
            "nodes_before": before["nodes"],
            "nodes_after": after["nodes"],
            "node_type_counts_before": before["node_type_counts"],
            "node_type_counts_after": after["node_type_counts"],
            "memory_bytes_before": before_bytes,
            "memory_bytes_after": target_path.stat().st_size,
            "compression_ratio_nodes": after["nodes"] / before["nodes"]
            if before["nodes"]
            else 1.0,
            "compression_ratio_bytes": target_path.stat().st_size / before_bytes
            if before_bytes
            else 1.0,
            "compression_latency_ms": latency_ms,
            "qwen_calls": 0, "qwen_latency_ms": 0.0,
            "streammeco_summary": summary,
        }
        write_json(row, target_dir / "metadata.json")
        metrics.append(row)
        print(f"COMPRESSION_COMPLETE q={index:02d}", flush=True)
    write_json(metrics, args.results / "compression_metrics.json")


def export_mandol(args, questions: list[dict]):
    for index, _qa in enumerate(questions, 1):
        source = args.results / "memory" / f"q{index:02d}_uncompressed" / "graph.pkl"
        root = args.results / "mandol_adapted" / f"q{index:02d}"
        interchange = root / "interchange"
        metrics_path = root / "export_metrics.json"
        if (interchange / "manifest.json").exists():
            continue
        root.mkdir(parents=True, exist_ok=True)
        started = time.perf_counter()
        manifest = export_graph(
            source,
            interchange,
            video_id=f"jake-day1-q{index:02d}",
            clip_duration_seconds=30.0,
            compressed=False,
        )
        latency_ms = (time.perf_counter() - started) * 1000
        write_json(
            {
                "export_ms": latency_ms,
                "embedding_free": True,
                "source_vectors_imported": False,
                "manifest": manifest.model_dump(),
            },
            metrics_path,
        )
        print(f"MANDOL_EXPORT_COMPLETE q={index:02d}", flush=True)


def _timed_parallel_get_embedding(model, texts, timeout=15):
    global _embedding_events
    texts = list(texts)

    def one(item):
        index, text = item
        started = time.perf_counter()
        embedding, tokens = chat_api.get_embedding_with_retry(model, text, timeout)
        event = {
            "index": index,
            "latency_ms": (time.perf_counter() - started) * 1000,
            "input_chars": len(text),
            "tokens": tokens,
            "dimension": len(embedding),
            "provider": "OpenRouter",
            "model": "openai/text-embedding-3-large",
        }
        with _embedding_lock:
            if _embedding_events is not None:
                _embedding_events.append(event)
        return embedding, tokens

    with ThreadPoolExecutor(max_workers=max(1, len(texts))) as executor:
        rows = list(executor.map(one, enumerate(texts)))
    return [row[0] for row in rows], sum(int(row[1] or 0) for row in rows)


def install_embedding_instrumentation():
    retrieve.parallel_get_embedding = _timed_parallel_get_embedding


model_call = runtime.text_call


def parse_prediction(text: str) -> str:
    matches = re.findall(r"(?:^|\b)([ABCD])(?:\b|[.)])", text.upper())
    return matches[-1] if matches else ""


def parse_action(text: str) -> tuple[str, str, str]:
    upper = text.upper()
    if "[ANSWER]" in upper:
        index = upper.index("[ANSWER]")
        return text[:index].strip(), "answer", text[index + len("[ANSWER]") :].strip()
    if "[SEARCH]" in upper:
        index = upper.index("[SEARCH]")
        return text[:index].strip(), "search", text[index + len("[SEARCH]") :].strip()
    raise ValueError(f"Controller output has no [ANSWER] or [SEARCH]: {text[:200]}")


def evidence_from_graph(graph, metrics: dict) -> list[dict]:
    scores = metrics.get("returned_node_scores", {})
    evidence = []
    for rank, node_id in enumerate(metrics.get("returned_node_ids", []), 1):
        node = graph.nodes[node_id]
        evidence.append(
            {
                "rank": rank,
                "node_id": node_id,
                "node_type": node.type,
                "timestamp": node.metadata.get("timestamp"),
                "score": scores.get(str(node_id)),
                "contents": node.metadata.get("contents", []),
            }
        )
    return evidence


def run_retrieval(graph, query: str, current_clips: list[int], top_k: int) -> tuple:
    global _embedding_events
    _embedding_events = []
    metrics = {}
    memories, current_clips, _scores = retrieve.search(
        graph,
        query,
        current_clips,
        topk=top_k,
        threshold=PROCESSING_CONFIG["retrieval_threshold"],
        metrics=metrics,
    )
    events = sorted(_embedding_events, key=lambda item: item["index"])
    _embedding_events = None
    metrics["embedding"] = {
        "call_count": len(events),
        "each_call_ms": [event["latency_ms"] for event in events],
        "total_ms": sum(event["latency_ms"] for event in events),
        "model": "openai/text-embedding-3-large",
        "provider": "OpenRouter",
        "calls": events,
    }
    metrics["retrieval"] = {
        "dense_ms": metrics.get("vector_search_ms", 0.0),
        "sparse_ms": 0.0,
        "StreamMeCo/TMR_ms": metrics.get("streammeco_tmr_scoring_ms", 0.0),
        "Mandol_search_ms": 0.0,
        "graph_traversal_ms": metrics.get("graph_node_selection_ms", 0.0),
        "rerank_ms": metrics.get("reranking_ms", 0.0),
        "other_ms": metrics.get("query_preparation_ms", 0.0),
        "TOTAL_RETRIEVAL_MS": metrics.get("retrieval_round_total_ms", 0.0),
    }
    metrics["evidence"] = evidence_from_graph(graph, metrics)
    return memories, current_clips, metrics


def one_shot(graph, question: dict, backend: str, args) -> dict:
    started = time.perf_counter()
    query_started = time.perf_counter()
    query = question["question"]
    query_ms = (time.perf_counter()-query_started)*1000
    memories, _clips, retrieval_metrics = run_retrieval(graph, query, [], args.top_k)
    retrieval_metrics.update(query_text=query, query_construction_ms=query_ms, query_generation_ms=0.0)
    prompt = (
        "Answer this multiple-choice question using only the retrieved memories. "
        "Return exactly one letter: A, B, C, or D.\n\n"
        f"Question:\n{question_text(question)}\n\nRetrieved memories:\n"
        + json.dumps(memories, ensure_ascii=False)
    )
    call = model_call(backend, prompt, args.qwen_url, "final_answer")
    prediction = parse_prediction(call["response"])
    return {
        "retrieval_query": query,
        "top_k": args.top_k,
        "retrieval_round_count": 1,
        "retrieval_rounds": [retrieval_metrics],
        "controller": {"call_count": 0, "each_call_ms": [], "total_ms": 0.0},
        "controller_calls": [],
        "final_answer_call": call,
        "final_answer_model_ms": call["latency_ms"],
        "FULL_QUESTION_TO_ANSWER_MS": (time.perf_counter() - started) * 1000,
        "retrieved_evidence": retrieval_metrics["evidence"],
        "retrieved_node_ids": retrieval_metrics.get("returned_node_ids", []),
        "prediction": prediction,
        "raw_answer": call["response"],
    }


def normal_controller(graph, question: dict, backend: str, args) -> dict:
    started = time.perf_counter()
    context: list[dict] = []
    current_clips: list[int] = []
    retrieval_rounds: list[dict] = []
    controller_calls: list[dict] = []
    final_answer = ""
    switch = False
    for step in range(PROCESSING_CONFIG["max_retrieval_steps"]):
        template = (
            prompt_generate_action_with_plan_new_direction
            if switch
            else prompt_generate_action_with_plan
        )
        prompt = template.format(
            question=question_text(question), knowledge=context, retrieval_plan=None
        )
        call = model_call(backend, prompt, args.qwen_url, "controller")
        call["step"] = step + 1
        controller_calls.append(call)
        reasoning, action_type, action_content = parse_action(call["response"])
        call["action_type"] = action_type
        call["action_content"] = action_content
        if action_type == "answer":
            final_answer = action_content
            break
        if step == PROCESSING_CONFIG["max_retrieval_steps"] - 1:
            prompt = prompt_answer_with_retrieval_final.format(
                question=question_text(question), information=context
            )
            call = model_call(backend, prompt, args.qwen_url, "forced_final_answer")
            call["step"] = step + 1
            controller_calls.append(call)
            raw = call["response"]
            final_answer = raw.split("[ANSWER]", 1)[-1].strip()
            break
        memories, current_clips, metrics = run_retrieval(
            graph, action_content, current_clips, args.top_k
        )
        metrics["round"] = len(retrieval_rounds) + 1
        metrics["controller_reasoning"] = reasoning
        retrieval_rounds.append(metrics)
        switch = not bool(memories) and PROCESSING_CONFIG.get("route_switch", True)
        context.append(
            {
                "reasoning": reasoning,
                "query": action_content,
                "retrieved memories": memories,
            }
        )
    if not controller_calls:
        raise RuntimeError("Normal controller made no model calls")
    evidence = [item for row in retrieval_rounds for item in row["evidence"]]
    return {
        "retrieval_query": [row["query_text"] for row in retrieval_rounds],
        "top_k": args.top_k,
        "retrieval_round_count": len(retrieval_rounds),
        "retrieval_rounds": retrieval_rounds,
        "controller": {
            "call_count": len(controller_calls),
            "each_call_ms": [row["latency_ms"] for row in controller_calls],
            "total_ms": sum(row["latency_ms"] for row in controller_calls),
        },
        "controller_calls": controller_calls,
        "final_answer_call": controller_calls[-1],
        "final_answer_model_ms": controller_calls[-1]["latency_ms"],
        "FULL_QUESTION_TO_ANSWER_MS": (time.perf_counter() - started) * 1000,
        "retrieved_evidence": evidence,
        "retrieved_node_ids": [item["node_id"] for item in evidence],
        "prediction": parse_prediction(final_answer),
        "raw_answer": final_answer,
    }


def run_eval(args, questions: list[dict], public_questions: list[dict]):
    if not args.method or not args.backend:
        raise ValueError("eval requires --method and --backend")
    output = args.results / OUTPUT_NAMES[(args.method, args.backend)]
    completed = {row["question_index"] for row in read_jsonl(output)} if output.exists() else set()
    install_embedding_instrumentation()
    from benchmarks.warm_query import prepare_warm_query
    for index, (qa, question) in enumerate(zip(questions, public_questions), 1):
        if index in completed:
            continue
        graph_path = (
            args.results / "streammeco_compressed" / f"q{index:02d}" / "graph.pkl"
            if args.method == "C"
            else args.results / "memory" / f"q{index:02d}_uncompressed" / "graph.pkl"
        )
        load_started = time.perf_counter()
        import hashlib
        snapshot_hash = hashlib.sha256(graph_path.read_bytes()).hexdigest()
        with graph_path.open("rb") as handle:
            graph = pickle.load(handle)
        load_ms = (time.perf_counter()-load_started)*1000
        warmup = prepare_warm_query(lambda probe: run_retrieval(graph,probe,[],args.top_k),
                                    args.results,args.method,index,load_ms)
        runtime.CONTEXT.update(question_id=question["id"], method=args.method)
        result = (
            normal_controller(graph, question, args.backend, args)
            if args.method == "A"
            else one_shot(graph, question, args.backend, args)
        )
        gold = qa["answer"]
        result.update(
            {
                "question_index": index,
                "question": question,
                "method": args.method,
                "model": args.backend,
                "memory": graph_counts(graph),
                "evaluated_graph_sha256": snapshot_hash,
                "latency_mode": "warm_retrieval_uncached_question",
                "snapshot_load_ms_excluded": load_ms,
                "warmup_ms_excluded": warmup["warmup_ms"],
                "gold_answer": gold,
                "correct": result["prediction"] == gold,
            }
        )
        append_jsonl(result, output)
        for round_index, event in enumerate(result["retrieval_rounds"], 1):
            append_jsonl(
                {
                    "question_index": index,
                    "method": args.method,
                    "model": args.backend,
                    "event": "retrieval",
                    "round": round_index,
                    **event,
                },
                args.results / "detailed_latency_events.jsonl",
            )
        for event in result["controller_calls"]:
            append_jsonl(
                {
                    "question_index": index,
                    "method": args.method,
                    "model": args.backend,
                    "event": "controller",
                    **event,
                },
                args.results / "detailed_latency_events.jsonl",
            )
        append_jsonl(
            {
                "question_index": index,
                "method": args.method,
                "model": args.backend,
                "event": "final_answer",
                **result["final_answer_call"],
            },
            args.results / "detailed_latency_events.jsonl",
        )
        print(
            f"EVAL_COMPLETE method={args.method} model={args.backend} q={index:02d} "
            f"prediction={result['prediction']} correct={result['correct']}",
            flush=True,
        )


def percentile95(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(0.95 * len(ordered)))]


def retrieval_total(row: dict) -> float:
    return sum(
        event.get("retrieval", {}).get(
            "TOTAL_RETRIEVAL_MS", event.get("retrieval_round_total_ms", 0.0)
        )
        for event in row.get("retrieval_rounds", [])
    )


def embedding_total(row: dict) -> float:
    return sum(
        event.get("embedding", {}).get("total_ms", event.get("embedding_ms", 0.0))
        for event in row.get("retrieval_rounds", [])
    )


from benchmarks.qwen_report import report, validate


def main() -> int:
    args = parse_args()
    args.results.mkdir(parents=True, exist_ok=True)
    args.work.mkdir(parents=True, exist_ok=True)
    mandol_dir = args.results / "mandol"
    mandol_dir.mkdir(parents=True, exist_ok=True)
    link = mandol_dir / "adapted_snapshots"
    if not link.exists() and not link.is_symlink():
        link.symlink_to("../mandol_adapted", target_is_directory=True)
    runtime.configure(args.results, args.phase)
    questions, public_questions = load_questions(args.qa)
    questions, public_questions = questions[:args.limit], public_questions[:args.limit]
    write_json(public_questions, args.results / "questions_without_gold.json")
    if args.phase == "build":
        try:
            build_memory(args, questions)
        finally:
            if getattr(args, "_prefetcher", None): args._prefetcher.close()
    elif args.phase == "compress":
        compress_snapshots(args, questions)
    elif args.phase == "export-mandol":
        export_mandol(args, questions)
    elif args.phase == "eval":
        run_eval(args, questions, public_questions)
    elif args.phase == "report":
        report(args)
    else:
        validate(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
