#!/usr/bin/env python3
"""Schedule original EgoEverything questions causally on the AEA stream."""

import argparse
import hashlib
import json
import math
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def build(manifest, source_rows, seed=42, interval=1200):
    entries = manifest["recordings"]
    by_name = {entry["sequence_id"]: entry for entry in entries}
    last_checkpoint = math.floor(manifest["total_duration_s"] / interval) * interval
    rows = []
    for index, original in enumerate(source_rows):
        entry = by_name.get(original["video_name"])
        if entry is None:
            continue
        keyframes = original.get("keyframes") or []
        if not keyframes:
            raise ValueError(f"Missing keyframes in VQA row {index}")
        local = float(keyframes[0]["timestamp"])
        if not 0 <= local <= entry["duration_s"] + 0.1:
            raise ValueError(f"Evidence outside recording {original['video_name']} row {index}: {local}")
        evidence = entry["global_start_s"] + local
        earliest = (math.floor(evidence / interval) + 1) * interval
        if earliest > last_checkpoint:
            continue
        digest = hashlib.sha256(f"{seed}:{index}:{original['video_name']}".encode()).digest()
        lag_group = int.from_bytes(digest[:4], "big") % 3
        minimum = (0, 1200, 3600)[lag_group]
        desired = max(earliest, math.ceil((evidence + minimum + 0.001) / interval) * interval)
        ask = min(desired, last_checkpoint)
        if ask <= evidence:
            raise ValueError("Noncausal question schedule")
        lag = ask - evidence
        bucket = "recent" if lag < 1200 else "medium" if lag <= 3600 else "long"
        current = next(e for e in entries if e["global_start_s"] < ask <= e["global_end_s"] + 0.001)
        rows.append({
            "question_id": f"egoeverything_{index:05d}", "source_video": original["video_name"],
            **original, "evidence_local_s": local, "evidence_global_s": round(evidence, 3),
            "ask_global_s": ask, "memory_lag_s": round(lag, 3), "lag_bucket": bucket,
            "source_session": entry["session_id"], "current_video": current["sequence_id"],
            "current_session": current["session_id"],
            "cross_clip": current["sequence_id"] != entry["sequence_id"],
            "cross_session": current["session_id"] != entry["session_id"],
        })
    for checkpoint in range(interval, last_checkpoint + 1, interval):
        deficit = max(0, 3 - sum(r["ask_global_s"] == checkpoint for r in rows))
        candidates = sorted(
            (r for r in rows if r["ask_global_s"] > checkpoint and r["evidence_global_s"] < checkpoint),
            key=lambda r: (r["ask_global_s"], r["question_id"]),
        )
        for row in candidates[:deficit]:
            row["ask_global_s"] = checkpoint
            row["memory_lag_s"] = round(checkpoint - row["evidence_global_s"], 3)
            lag = row["memory_lag_s"]
            row["lag_bucket"] = "recent" if lag < 1200 else "medium" if lag <= 3600 else "long"
            current = next(e for e in entries if e["global_start_s"] < checkpoint <= e["global_end_s"] + 0.001)
            row["current_video"] = current["sequence_id"]
            row["current_session"] = current["session_id"]
            row["cross_clip"] = current["sequence_id"] != row["source_video"]
            row["cross_session"] = current["session_id"] != row["source_session"]
    return {"seed": seed, "checkpoint_interval_s": interval,
            "schedule_policy": "derived causal ask times; original QA fields unchanged",
            "source": "Egoeverything_VQA.json", "questions": sorted(rows, key=lambda r: (r["ask_global_s"], r["question_id"]))}


def main():
    parser = argparse.ArgumentParser()
    dataset = ROOT / "benchmark" / "aea_6h"
    parser.add_argument("--manifest", type=Path, default=dataset / "aea_6h_manifest.json")
    parser.add_argument("--qa", type=Path, default=dataset / "Egoeverything_VQA.json")
    parser.add_argument("--out", type=Path, default=dataset / "aea_6h_qa_schedule.json")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    schedule = build(json.loads(args.manifest.read_text()), json.loads(args.qa.read_text()), args.seed)
    args.out.write_text(json.dumps(schedule, indent=2, ensure_ascii=False) + "\n")
    rows = schedule["questions"]
    print(f"Scheduled {len(rows)} questions; lags {dict(Counter(r['lag_bucket'] for r in rows))}; "
          f"cross-clip {sum(r['cross_clip'] for r in rows)}; "
          f"cross-session {sum(r['cross_session'] for r in rows)}")
    print("Per checkpoint:", dict(sorted(Counter(r["ask_global_s"] for r in rows).items())))


if __name__ == "__main__":
    main()
