"""First-channel 16 kHz extraction with content-addressed ECAPA caches."""

import hashlib
import json
import math
import time
from pathlib import Path

import numpy as np

from .scoring import matrix

RATE = 16000
LENGTH = 64000
HOP = 24000


def windows(length):
    if length <= LENGTH:
        return [(0, length)]
    if length <= LENGTH + HOP:
        return [(0, LENGTH), (length - LENGTH, length)]
    starts = list(range(0, length - LENGTH + 1, HOP))
    if starts[-1] != length - LENGTH:
        starts.append(length - LENGTH)
    return [(start, start + LENGTH) for start in starts]


def file_hash(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class AudioExtractor:
    def __init__(self, encoder, fingerprint, cache_dir, minimum_samples=0):
        self.encoder = encoder
        self.fingerprint = fingerprint
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.minimum_samples = minimum_samples
        self.decoded = {}
        self.hashes = {}
        self.cache_hits = 0
        self.padded_windows = 0

    def _load(self, path):
        path = str(Path(path).resolve())
        if path not in self.decoded:
            from math import gcd

            import soundfile as sf
            from scipy.signal import resample_poly

            data, rate = sf.read(path, always_2d=True, dtype="float32")
            mono = data[:, 0]
            if rate != RATE:
                factor = gcd(rate, RATE)
                mono = resample_poly(mono, RATE // factor, rate // factor).astype(
                    np.float32
                )
            self.decoded[path] = (mono, rate, len(data) / rate)
            self.hashes[path] = file_hash(path)
        return self.decoded[path]

    def extract(self, ref):
        start, end = ref["start_s"], ref["end_s"]
        path = str(Path(ref["audio_path"]).resolve())
        data, _, duration = self._load(path)
        if (
            not all(math.isfinite(v) for v in (start, end))
            or start < 0
            or start >= end
            or end > duration + 1e-9
        ):
            raise ValueError("invalid audio interval")
        first = math.floor(start * RATE)
        last = min(len(data), math.ceil(end * RATE))
        crop = data[first:last]
        if not len(crop):
            raise ValueError("empty audio crop")
        key = hashlib.sha256(
            json.dumps(
                [
                    self.hashes[path],
                    start,
                    end,
                    self.fingerprint,
                    RATE,
                    LENGTH,
                    HOP,
                    self.minimum_samples,
                ]
            ).encode()
        ).hexdigest()
        cached = self.cache_dir / (key + ".npy")
        began = time.perf_counter()
        if cached.exists():
            try:
                result = matrix(np.load(cached, allow_pickle=False))
            except (ValueError, OSError) as exc:
                raise EmbeddingError(f"invalid cached embedding: {exc}") from exc
            self.cache_hits += 1
            return result, True, 0.0
        try:
            rows = []
            for a, b in windows(len(crop)):
                wave = crop[a:b]
                if len(wave) < self.minimum_samples:
                    wave = np.pad(wave, (0, self.minimum_samples - len(wave)))
                    self.padded_windows += 1
                rows.append(self.encoder.encode(wave))
            result = matrix(rows)
        except (ValueError, RuntimeError) as exc:
            raise EmbeddingError(str(exc)) from exc
        temporary = cached.with_suffix(".tmp.npy")
        np.save(temporary, result)
        temporary.replace(cached)
        return result, False, (time.perf_counter() - began) * 1000


class EmbeddingError(ValueError):
    """Encoder output or inference failure, distinct from an invalid interval."""
