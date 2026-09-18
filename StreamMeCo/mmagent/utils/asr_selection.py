"""One configured transcription/diarization provider per construction run."""

import hashlib
import json
import time


def selected_asr_provider(processing_config, api_config):
    if "asr_providers" in processing_config:
        raise ValueError("asr_providers is obsolete; configure one asr_provider")
    name = processing_config.get("asr_provider")
    if not isinstance(name, str) or not name.strip() or name != name.strip():
        raise ValueError("configure exactly one asr_provider alias")
    settings = api_config.get(name)
    if not isinstance(settings, dict) or settings.get("provider") not in {"deepgram", "openrouter"}:
        raise ValueError(f"unsupported ASR provider alias: {name}")
    if settings.get("capability") and settings["capability"] != "transcription":
        raise ValueError(f"provider is not a transcription model: {name}")
    if not settings.get("model") or not settings.get("base_url"):
        raise ValueError(f"incomplete transcription provider configuration: {name}")
    return name


def run_selected_asr(provider, request):
    """Keep the existing prefetch timing tuple without calling another provider."""
    started = time.perf_counter()
    try:
        segments = request(provider)
        error = None
    except Exception as exc:
        segments = None
        error = f"{provider}: {type(exc).__name__}: {exc}"
    elapsed = (time.perf_counter() - started) * 1000
    return (
        {provider: segments} if error is None else {},
        [error] if error else [],
        {provider: elapsed},
        elapsed,
    )


def selected_segments(provider, provider_results):
    if set(provider_results) != {provider}:
        raise ValueError("prepared ASR results do not match the selected provider")
    if any(
        not isinstance(segment, dict)
        or segment.get("asr_provider", provider) != provider
        or segment.get("asr_sources", [provider]) != [provider]
        for segment in provider_results[provider]
    ):
        raise ValueError("ASR segment contains another provider or fused sources")
    return [
        dict(segment, asr_provider=provider, asr_sources=[provider])
        for segment in provider_results[provider]
    ]


def cached_voice_segments(path, provider, audio_data):
    """Return only cache rows bound to this provider and these exact audio bytes."""
    try:
        with open(f"{path}.provider.json", encoding="utf-8") as handle:
            metadata = json.load(handle)
        with open(path, encoding="utf-8") as handle:
            segments = json.load(handle)
    except (OSError, ValueError):
        return None
    if metadata != {
        "asr_provider": provider,
        "audio_sha256": hashlib.sha256(audio_data).hexdigest(),
    }:
        return None
    if not isinstance(segments, list) or any(
        not isinstance(segment, dict)
        or segment.get("asr_provider") != provider
        or segment.get("asr_sources") != [provider]
        or not isinstance(segment.get("audio_segment"), str)
        for segment in segments
    ):
        return None
    return segments
