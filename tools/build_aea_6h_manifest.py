#!/usr/bin/env python3
"""Select complete, ordered AEA RGB recordings using measured MP4 durations."""

import argparse
import concurrent.futures
import json
import re
import subprocess
from collections import Counter
from pathlib import Path

PATTERN = re.compile(r"loc(\d+)_script(\d+)_seq(\d+)_rec(\d+)$")
ROOT = Path(__file__).resolve().parents[1]


def probe(item):
    sequence_id, source = item
    url = source["video_main_rgb"]["download_url"]
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "format=duration:stream=codec_type,codec_name,channels,sample_rate",
         "-of", "json", url], capture_output=True, text=True, timeout=90, check=True
    )
    data = json.loads(result.stdout)
    duration = float(data["format"]["duration"])
    audio = [s for s in data["streams"] if s["codec_type"] == "audio"]
    if duration <= 0:
        raise ValueError(f"Invalid duration: {sequence_id}")
    return sequence_id, duration, bool(audio and audio[0].get("sample_rate") and audio[0].get("channels"))


def build(urls, qa, measurements, target):
    names = urls["sequences"]
    qa_counts = Counter(row["video_name"] for row in qa)
    groups = {}
    for name in names:
        match = PATTERN.fullmatch(name)
        if not match:
            raise ValueError(f"Unexpected sequence ID: {name}")
        loc, script, seq, rec = map(int, match.groups())
        groups.setdefault((loc, script, rec), []).append((seq, name))
    for members in groups.values():
        members.sort()
    inventory = []
    for (loc, script, rec), members in sorted(groups.items()):
        for seq, name in members:
            duration, audio = measurements[name]
            inventory.append({"sequence_id": name, "location": loc, "script": script,
                              "seq": seq, "rec": rec, "duration_s": duration,
                              "explorer_url": f"https://explorer.projectaria.com/aea/{name}",
                              "has_ego_everything_qa": qa_counts[name] > 0,
                              "audio_in_mp4": audio})
    order = sorted(groups, key=lambda k: (k[2] != 1, k[1] not in (1, 4, 5), k[0], k[1], k[2]))
    selected = []
    elapsed = 0.0
    for loc, script, rec in order:
        for seq, name in groups[(loc, script, rec)]:
            duration, audio = measurements[name]
            boundary = not selected or selected[-1]["session_id"] != f"loc{loc}_script{script}_rec{rec}"
            selected.append({
                "stream_index": len(selected), "sequence_id": name, "location": loc,
                "script": script, "seq": seq, "rec": rec,
                "session_id": f"loc{loc}_script{script}_rec{rec}",
                "session_boundary": boundary, "alternate_wearer": rec != 1,
                "duration_s": duration, "global_start_s": round(elapsed, 3),
                "global_end_s": round(elapsed + duration, 3),
                "has_questions": qa_counts[name] > 0, "question_count": qa_counts[name],
                "audio_in_mp4": audio, "video_path": f"videos/{name}.mp4",
                "video_size_bytes": names[name]["video_main_rgb"]["file_size_bytes"],
                "explorer_url": f"https://explorer.projectaria.com/aea/{name}",
            })
            elapsed += duration
        if elapsed >= target:
            break
    return {"source": "Aria Everyday Activities", "target_duration_s": target,
            "total_duration_s": round(elapsed, 3), "discovered_count": len(names),
            "selected_count": len(selected), "video_size_bytes": sum(x["video_size_bytes"] for x in selected),
            "inventory": inventory, "recordings": selected}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--urls", type=Path, default=ROOT / "aea_6h" / "aea_download_urls.json")
    parser.add_argument("--qa", type=Path, default=ROOT / "aea_6h" / "Egoeverything_VQA.json")
    parser.add_argument("--out", type=Path, default=ROOT / "aea_6h" / "aea_6h_manifest.json")
    parser.add_argument("--target", type=float, default=21600)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    urls = json.loads(args.urls.read_text())
    qa = json.loads(args.qa.read_text())
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        results = dict((name, (duration, audio)) for name, duration, audio in pool.map(
            probe, urls["sequences"].items()))
    manifest = build(urls, qa, results, args.target)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Discovered {manifest['discovered_count']}; selected {manifest['selected_count']} "
          f"({manifest['total_duration_s'] / 3600:.3f} h, {manifest['video_size_bytes'] / 2**30:.2f} GiB)")
    for item in manifest["recordings"]:
        print(f"{item['stream_index']:3} {item['sequence_id']:32} {item['duration_s']:8.3f}s "
              f"through {item['global_end_s']:9.3f}s QA={item['question_count']:2} "
              f"audio={item['audio_in_mp4']} boundary={item['session_boundary']}")


if __name__ == "__main__":
    main()
