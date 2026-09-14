"""Gemini 3.8 VLM adapter for the OpenAI-compatible 302.ai endpoint."""
import base64
import json
import math
import os
from pathlib import Path

import cv2
import httpx
import openai
import time


ROOT = Path(__file__).resolve().parents[2]
API_CONFIG = json.loads((ROOT / "configs/api_config.json").read_text())
PROCESSING_CONFIG = json.loads((ROOT / "configs/processing_config.json").read_text())
MODEL = "gemini-3.8-flash"


def _client():
    config = API_CONFIG[MODEL]
    api_key = os.environ.get(config.get("api_key_env", "")) or config.get("api_key")
    if not api_key:
        raise ValueError(f"Missing API key for {MODEL}")
    return openai.OpenAI(api_key=api_key, base_url=config["base_url"])


def _resize_for_pixel_cap(frame, max_pixels):
    height, width = frame.shape[:2]
    pixels = height * width
    if pixels <= max_pixels:
        return frame
    scale = math.sqrt(max_pixels / pixels)
    return cv2.resize(
        frame,
        (max(1, int(width * scale)), max(1, int(height * scale))),
        interpolation=cv2.INTER_AREA,
    )


def sample_video(video_path, fps=None, max_pixels=None, jpeg_quality=85):
    """Sample timestamped JPEG frames with the same defaults as local Qwen."""
    fps = float(fps or PROCESSING_CONFIG.get("qwen_video_fps", 2))
    max_pixels = int(max_pixels or PROCESSING_CONFIG.get("qwen_video_max_pixels", 151200))
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise ValueError(f"Cannot open video: {video_path}")
    source_fps = capture.get(cv2.CAP_PROP_FPS) or 20.0
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = frame_count / source_fps if frame_count else 0.0
    timestamps = []
    timestamp = 0.0
    while timestamp < duration:
        timestamps.append(timestamp)
        timestamp += 1.0 / fps
    frames = []
    try:
        for timestamp in timestamps:
            capture.set(cv2.CAP_PROP_POS_MSEC, timestamp * 1000)
            ok, frame = capture.read()
            if not ok:
                continue
            frame = _resize_for_pixel_cap(frame, max_pixels)
            ok, encoded = cv2.imencode(
                ".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), int(jpeg_quality)]
            )
            if ok:
                frames.append((timestamp, base64.b64encode(encoded).decode("ascii")))
    finally:
        capture.release()
    if not frames:
        raise ValueError(f"No frames decoded from video: {video_path}")
    return frames, duration


def generate_messages(inputs, fps=None, max_pixels=None):
    """Convert StreamMeCo mixed inputs to OpenAI-compatible multimodal messages."""
    content = []
    media = {"frame_count": 0, "video_duration_seconds": 0.0}
    for item in inputs:
        value = item.get("content")
        if not value:
            continue
        item_type = item["type"]
        if item_type == "text":
            content.append({"type": "text", "text": str(value)})
        elif item_type in {"images/jpeg", "images/png"}:
            for image in value:
                label, encoded = image if not isinstance(image, str) else (None, image)
                if label:
                    content.append({"type": "text", "text": str(label)})
                content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{encoded}", "detail": "low"},
                })
        elif item_type in {"video_url", "video_base64/mp4", "video_base64/webm"}:
            frames, duration = sample_video(value, fps=fps, max_pixels=max_pixels)
            media["frame_count"] += len(frames)
            media["video_duration_seconds"] += duration
            for timestamp, encoded in frames:
                content.append({"type": "text", "text": f"Video frame at {timestamp:.2f}s"})
                content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{encoded}", "detail": "low"},
                })
        else:
            raise ValueError(f"Unsupported Gemini input type: {item_type}")
    return [{"role": "user", "content": content}], media


def get_response(messages, timeout=600, max_tokens=8192):
    response = _client().chat.completions.create(
        model=MODEL,
        messages=messages,
        temperature=PROCESSING_CONFIG["temperature"],
        max_tokens=max_tokens,
        timeout=timeout,
    )
    usage = response.usage.total_tokens if response.usage else None
    return response.choices[0].message.content or "", usage


def post_302_direct(path, payload, timeout=600, direct_ip=None):
    """Call 302.ai from restricted GPU hosts using the verified direct-IP route."""
    direct_ip = direct_ip or os.environ.get("API_302_DIRECT_IP", "20.255.184.187")
    started = time.perf_counter()
    with httpx.Client(verify=False, trust_env=False, timeout=timeout) as direct_client:
        response = direct_client.post(
            f"https://{direct_ip}/v1/{path.lstrip('/')}",
            headers={
                "Host": "api.302.ai",
                "Authorization": f"Bearer {_client().api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
    latency_ms = (time.perf_counter() - started) * 1000
    response.raise_for_status()
    return response.json(), latency_ms


def get_response_direct(messages, timeout=600, max_tokens=8192):
    payload = {
        "model": MODEL,
        "messages": messages,
        "temperature": PROCESSING_CONFIG["temperature"],
        "max_tokens": max_tokens,
    }
    response, latency_ms = post_302_direct(
        "chat/completions", payload, timeout=timeout
    )
    usage = (response.get("usage") or {}).get("total_tokens")
    content = response["choices"][0]["message"].get("content") or ""
    return content, usage, latency_ms, response


def get_embeddings_direct(texts, timeout=120):
    response, latency_ms = post_302_direct(
        "embeddings",
        {"model": "text-embedding-3-large", "input": texts},
        timeout=timeout,
    )
    ordered = sorted(response["data"], key=lambda item: item["index"])
    return [item["embedding"] for item in ordered], latency_ms, response
