#!/usr/bin/env python3
"""Call MAI-Transcribe-2 through OpenRouter's Azure diarization endpoint."""
from __future__ import annotations
import argparse, base64, json, os
from pathlib import Path
import httpx

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("audio", type=Path)
    ap.add_argument("--format", default=None)
    ap.add_argument("--output", type=Path, default=None)
    args = ap.parse_args()
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise SystemExit("Set OPENROUTER_API_KEY before running this command")
    payload = {"model": "microsoft/mai-transcribe-2", "input_audio": {"data": base64.b64encode(args.audio.read_bytes()).decode("ascii"), "format": args.format or args.audio.suffix.lstrip(".").lower()}, "response_format": "verbose_json", "provider": {"only": ["azure"], "options": {"azure": {"diarization": {"enabled": True}}}}}
    response = httpx.post("https://openrouter.ai/api/v1/audio/transcriptions", headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json", "HTTP-Referer": "https://github.com/Celina-love-sweet/StreamMeCo", "X-Title": "StreamMeCo identity setup"}, json=payload, timeout=180)
    response.raise_for_status()
    result = response.json()
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
