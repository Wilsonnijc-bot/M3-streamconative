#!/usr/bin/env python3
"""Copy verified local AEA MP4s to a GPU VM in parallel, then verify there."""

import argparse
import concurrent.futures
import json
import re
import subprocess
from pathlib import Path

from download_aea_6h import inspect_media, verify


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--urls", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--host", required=True, help="SSH destination, e.g. ubuntu@host")
    parser.add_argument("--key", type=Path, required=True)
    parser.add_argument("--destination", required=True, help="Remote aea_6h directory")
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    sources = json.loads(args.urls.read_text())["sequences"]
    entries = json.loads(args.manifest.read_text())["recordings"]
    ssh = ["ssh", "-o", "BatchMode=yes", "-i", str(args.key), args.host]
    scp = ["scp", "-q", "-i", str(args.key)]
    remote = args.destination.rstrip("/")
    if not remote.startswith("/") or " " in remote:
        parser.error("Remote destination must be an absolute path without spaces")

    def send(entry):
        name = entry["sequence_id"]
        if not re.fullmatch(r"loc\d+_script\d+_seq\d+_rec\d+", name):
            raise ValueError(f"Invalid sequence ID: {name}")
        source = sources[name]["video_main_rgb"]
        local = args.source / "videos" / f"{name}.mp4"
        if not local.exists():
            return f"WAITING {name}"
        if not verify(local, source) or not inspect_media(local, entry["duration_s"]):
            raise ValueError(f"Local media verification failed: {name}")
        target = f"{remote}/videos/{name}.mp4"
        digest = source["sha1sum"]
        existing = subprocess.run(ssh + [f"test -f {target} && sha1sum {target}"],
                                  capture_output=True, text=True)
        if existing.returncode == 0 and existing.stdout.split()[0] == digest:
            return f"VERIFIED {name}"
        temporary = target + ".incoming"
        subprocess.run(scp + [str(local), f"{args.host}:{temporary}"], check=True)
        result = subprocess.run(ssh + [f"sha1sum {temporary}"],
                                capture_output=True, text=True, check=True)
        if result.stdout.split()[0] != digest:
            subprocess.run(ssh + [f"rm -f {temporary}"], check=True)
            raise ValueError(f"Remote checksum failed: {name}")
        subprocess.run(ssh + [f"mv {temporary} {target}"], check=True)
        return f"TRANSFERRED {name}"

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        for result in concurrent.futures.as_completed([pool.submit(send, e) for e in entries]):
            print(result.result(), flush=True)


if __name__ == "__main__":
    main()
