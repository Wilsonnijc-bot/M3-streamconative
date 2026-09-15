#!/usr/bin/env python3
"""Persistent local Qwen text-generation server with CUDA-synchronized timing."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

import torch

from mmagent.utils.chat_qwen import generate_messages, get_response


def _generate(prompt: str, enable_thinking: bool, max_new_tokens: int) -> dict:
    messages = generate_messages([{"type": "text", "content": prompt}])
    if torch.cuda.is_available():
        torch.cuda.synchronize()
    started = time.perf_counter()
    response, total_tokens, details = get_response(
        messages,
        enable_thinking=enable_thinking,
        max_new_tokens=max_new_tokens,
        return_details=True,
    )
    if torch.cuda.is_available():
        torch.cuda.synchronize()
    latency_ms = (time.perf_counter() - started) * 1000
    output_tokens = int(details.get("output_tokens") or 0)
    return {
        "response": response,
        "latency_ms": latency_ms,
        "input_tokens": max(0, int(total_tokens) - output_tokens),
        "output_tokens": output_tokens,
        "total_tokens": int(total_tokens),
        "model": "Qwen/Qwen3.5-4B",
        "provider": "local CUDA",
        "cuda_synchronized": bool(torch.cuda.is_available()),
        "generation": details,
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "StreamMeCoQwen/1"

    def log_message(self, fmt: str, *args) -> None:
        print(
            f"[{time.strftime('%Y-%m-%dT%H:%M:%S%z')}] " + fmt % args,
            flush=True,
        )

    def _json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path != "/health":
            self._json(404, {"error": "not found"})
            return
        self._json(
            200,
            {
                "status": "ok",
                "model": "Qwen/Qwen3.5-4B",
                "cuda": torch.cuda.is_available(),
                "device": torch.cuda.get_device_name(0)
                if torch.cuda.is_available()
                else None,
            },
        )

    def do_POST(self) -> None:
        if self.path != "/generate":
            self._json(404, {"error": "not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length))
            prompt = str(payload["prompt"])
            if not prompt.strip():
                raise ValueError("prompt is empty")
            result = _generate(
                prompt,
                bool(payload.get("enable_thinking", True)),
                int(payload.get("max_new_tokens", 768)),
            )
            self._json(200, result)
        except Exception as exc:
            self._json(
                500,
                {"error": type(exc).__name__, "message": str(exc)},
            )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--warmup", action=argparse.BooleanOptionalAction, default=True)
    args = parser.parse_args()
    if args.warmup:
        result = _generate("Return exactly OK.", False, 8)
        print(
            json.dumps(
                {
                    "event": "QWEN_SERVER_WARMUP",
                    "latency_ms": result["latency_ms"],
                    "output_tokens": result["output_tokens"],
                }
            ),
            flush=True,
        )
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(
        f"QWEN_SERVER_READY host={args.host} port={args.port}",
        flush=True,
    )
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
