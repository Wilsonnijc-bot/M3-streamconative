"""Content-addressed single-provider ASR cache for online ingestion."""

import base64
import hashlib
import json
from pathlib import Path
import time

from .utils.asr_selection import run_selected_asr
from .utils.chat_api import transcribe_audio_with_retry


def _digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False))
    temporary.replace(path)


class PreparedASRCache:
    """Run one ASR request per audio payload and reuse its diarized segments."""

    def __init__(self, directory, provider, provider_config, display_root=None):
        self.directory = Path(directory)
        self.provider = provider
        self.provider_config = {
            key: value
            for key, value in provider_config.items()
            if key not in {"api_key", "api_key_env"}
        }
        self.display_root = Path(display_root) if display_root else None

    def get(self, encoded_audio):
        if not encoded_audio:
            return None, {
                "cache_hit": False,
                "cache_path": None,
                "lookup_or_request_ms": 0.0,
                "timing_scope": "no audio payload",
            }
        audio = base64.b64decode(encoded_audio)
        key = _digest(
            {
                "audio_sha256": hashlib.sha256(audio).hexdigest(),
                "provider": self.provider,
                "provider_config": self.provider_config,
            }
        )
        path = self.directory / f"{key}.json"
        started = time.perf_counter()
        cache_hit = path.exists()
        if cache_hit:
            stored = json.loads(path.read_text())
            if not isinstance(stored, list) or len(stored) != 4:
                raise ValueError("invalid prepared ASR cache record")
            prepared = (stored[0], stored[1], {self.provider: None}, None)
        else:
            prepared = run_selected_asr(
                self.provider,
                lambda name: transcribe_audio_with_retry(
                    name, audio, audio_format="wav"
                ),
            )
            _atomic_json(path, prepared)
        provider_results, errors, _provider_ms, _total_ms = prepared
        if self.provider not in provider_results or errors:
            raise RuntimeError("selected ASR provider failed: " + "; ".join(errors))
        displayed = path
        if self.display_root is not None:
            displayed = path.relative_to(self.display_root)
        return prepared, {
            "cache_hit": cache_hit,
            "cache_path": str(displayed),
            "lookup_or_request_ms": (time.perf_counter() - started) * 1000,
            "timing_scope": (
                "shared event ASR; cached request duration not reported as new inference"
            ),
            "provider": self.provider,
        }
