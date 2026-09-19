#!/usr/bin/env python3
"""Download only selected AEA RGB MP4s with embedded audio, resumably."""

import argparse
import concurrent.futures
import hashlib
import json
import os
import shutil
import subprocess
import urllib.request
from pathlib import Path


def verify(path, source):
    if not path.exists() or path.stat().st_size != source["file_size_bytes"]:
        return False
    digest = hashlib.sha1()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest() == source["sha1sum"]


def inspect_media(path, expected_duration):
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "format=duration:stream=index,codec_type,codec_name,channels,sample_rate,duration,start_time",
         "-of", "json", str(path)], capture_output=True, text=True, check=True
    )
    data = json.loads(result.stdout)
    streams = data["streams"]
    video = next((s for s in streams if s["codec_type"] == "video"), None)
    audio = next((s for s in streams if s["codec_type"] == "audio" and
                  int(s.get("channels", 0)) > 0 and int(s.get("sample_rate", 0)) > 0), None)
    if not video or not audio or abs(float(data["format"]["duration"]) - expected_duration) > 0.2:
        return False
    for stream in (video, audio):
        if "duration" in stream and abs(float(stream["duration"]) - expected_duration) > 1.0:
            return False
    if abs(float(video.get("start_time", 0)) - float(audio.get("start_time", 0))) > 0.5:
        return False
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--urls", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    sources = json.loads(args.urls.read_text())["sequences"]
    manifest = json.loads(args.manifest.read_text())
    entries = manifest["recordings"]
    if any(not entry["audio_in_mp4"] for entry in entries):
        raise SystemExit("Selected MP4 lacks audio; refusing RGB-only corpus. VRS extraction is not configured.")
    required = sum(sources[e["sequence_id"]]["video_main_rgb"]["file_size_bytes"] for e in entries)
    destination = args.destination
    videos = destination / "videos"
    videos.mkdir(parents=True, exist_ok=True)
    remaining = sum(sources[e["sequence_id"]]["video_main_rgb"]["file_size_bytes"]
                    for e in entries if not verify(videos / f"{e['sequence_id']}.mp4",
                                                   sources[e["sequence_id"]]["video_main_rgb"]))
    free = shutil.disk_usage(destination).free
    print(f"Selected {len(entries)} MP4s: {required / 2**30:.2f} GiB, "
          f"remaining {remaining / 2**30:.2f} GiB, free {free / 2**30:.2f} GiB", flush=True)
    if free < remaining + 1024**3:
        raise SystemExit("Insufficient free space (1 GiB reserve required)")
    def download(item):
        index, entry = item
        name = entry["sequence_id"]
        source = sources[name]["video_main_rgb"]
        target = videos / f"{name}.mp4"
        if verify(target, source) and inspect_media(target, entry["duration_s"]):
            return f"[{index}/{len(entries)}] verified {name}"
        temp = target.with_suffix(".mp4.part")
        temp.unlink(missing_ok=True)
        try:
            for attempt in range(3):
                try:
                    with urllib.request.urlopen(source["download_url"], timeout=60) as response, temp.open("wb") as output:
                        shutil.copyfileobj(response, output, length=1024 * 1024)
                    break
                except Exception:
                    temp.unlink(missing_ok=True)
                    if attempt == 2:
                        raise
            if not verify(temp, source) or not inspect_media(temp, entry["duration_s"]):
                raise ValueError(f"Checksum, A/V stream or sync verification failed: {name}")
            os.replace(temp, target)
            return f"[{index}/{len(entries)}] downloaded {name}"
        except Exception:
            temp.unlink(missing_ok=True)
            raise
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        for future in concurrent.futures.as_completed(
                [pool.submit(download, item) for item in enumerate(entries, 1)]):
            print(future.result(), flush=True)
    shutil.copyfile(args.manifest, destination / "aea_6h_manifest.json")
    print("All selected MP4s verified; no VRS or other sensor products downloaded.")


if __name__ == "__main__":
    main()
