"""Fail-closed OpenAI-compatible embedding client for 302.AI."""

from __future__ import annotations

import os
import time
from collections.abc import Callable, Sequence
from typing import Any

import numpy as np
from openai import OpenAI

DEFAULT_BASE_URL = "https://api.302.ai/v1"
DEFAULT_MODEL = "Qwen/Qwen3-Embedding-0.6B"
DEFAULT_DIMENSION = 1024


class EmbeddingProviderError(RuntimeError):
    """Raised when the embedding provider cannot return validated vectors."""


def resolve_302_api_key(explicit_key: str | None = None) -> str:
    key = explicit_key or os.getenv("M3_MANDOL_302_API_KEY") or os.getenv("API_302_KEY")
    if not key or not key.strip():
        raise ValueError("Set M3_MANDOL_302_API_KEY (preferred) or API_302_KEY")
    return key.strip()


class OpenAICompatible302EmbeddingAdapter:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
        model: str = DEFAULT_MODEL,
        expected_dimension: int = DEFAULT_DIMENSION,
        max_retries: int = 2,
        timeout_seconds: float = 60.0,
        retry_backoff_seconds: float = 0.5,
        client: Any | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if expected_dimension <= 0 or max_retries < 0 or timeout_seconds <= 0:
            raise ValueError("Invalid embedding adapter limits")
        self.model = model
        self.expected_dimension = expected_dimension
        self.max_retries = max_retries
        self.retry_backoff_seconds = retry_backoff_seconds
        self._sleep = sleep
        self._client = client or OpenAI(
            api_key=resolve_302_api_key(api_key),
            base_url=base_url.rstrip("/"),
            timeout=timeout_seconds,
            max_retries=0,
        )

    def encode(
        self, text_or_batch: str | Sequence[str], batch_size: int = 32, **_: Any
    ) -> np.ndarray:
        is_single = isinstance(text_or_batch, str)
        texts = [text_or_batch] if is_single else list(text_or_batch)
        if batch_size <= 0:
            raise ValueError("batch_size must be positive")
        if not texts:
            return np.empty((0, self.expected_dimension), dtype=np.float32)
        if any(not isinstance(text, str) or not text.strip() for text in texts):
            raise ValueError("Embedding inputs must be non-empty strings")

        vectors: list[np.ndarray] = []
        for offset in range(0, len(texts), batch_size):
            vectors.extend(self._embed_batch(texts[offset : offset + batch_size]))
        matrix = np.stack(vectors).astype(np.float32, copy=False)
        return matrix[0] if is_single else matrix

    def _embed_batch(self, texts: list[str]) -> list[np.ndarray]:
        for attempt in range(self.max_retries + 1):
            try:
                response = self._client.embeddings.create(model=self.model, input=texts)
                data = list(getattr(response, "data", []))
                if len(data) != len(texts):
                    raise EmbeddingProviderError(
                        f"Embedding response count mismatch: expected {len(texts)}, got {len(data)}"
                    )
                indexed = sorted(data, key=lambda item: int(getattr(item, "index", -1)))
                if [int(getattr(item, "index", -1)) for item in indexed] != list(
                    range(len(texts))
                ):
                    raise EmbeddingProviderError(
                        "Embedding response indexes are missing or duplicated"
                    )
                vectors = [
                    np.asarray(item.embedding, dtype=np.float32) for item in indexed
                ]
                for vector in vectors:
                    if vector.ndim != 1 or vector.shape[0] != self.expected_dimension:
                        raise EmbeddingProviderError(
                            f"Embedding dimension mismatch: expected {self.expected_dimension}, got {vector.shape}"
                        )
                    if not np.isfinite(vector).all() or not np.any(vector):
                        raise EmbeddingProviderError(
                            "Embedding response contains a non-finite or zero vector"
                        )
                return vectors
            except Exception as exc:
                status_code = getattr(exc, "status_code", None)
                retryable = status_code not in {400, 401, 403, 404, 422}
                if attempt >= self.max_retries or not retryable:
                    if isinstance(exc, EmbeddingProviderError):
                        raise
                    raise EmbeddingProviderError(
                        f"302.AI embedding request failed: {type(exc).__name__}"
                    ) from exc
                self._sleep(self.retry_backoff_seconds * (2**attempt))
        raise AssertionError("unreachable")

