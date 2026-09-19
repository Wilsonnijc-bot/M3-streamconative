"""OpenRouter request helpers for the M3 embedding and reranking path."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

import httpx

DEFAULT_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_RERANK_MODEL = "qwen/qwen3-reranker-0.6b"


def rerank_documents(
    query: str,
    documents: Sequence[str],
    top_n: int,
    *,
    api_key: str,
    base_url: str = DEFAULT_OPENROUTER_BASE_URL,
    post: Callable[..., Any] = httpx.post,
) -> tuple[list[dict[str, Any]], Any]:
    """Call OpenRouter's dedicated reranking endpoint and validate its shape."""
    if not query.strip():
        raise ValueError("rerank query must be non-empty")
    if not documents:
        return [], None
    if top_n <= 0:
        raise ValueError("top_n must be positive")

    payload = {
        "model": DEFAULT_RERANK_MODEL,
        "query": query,
        "documents": list(documents),
        "top_n": min(top_n, len(documents)),
    }
    response = post(
        f"{base_url.rstrip('/')}/rerank",
        timeout=300,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
    )
    response.raise_for_status()
    body = response.json()
    results = body.get("results")
    if not isinstance(results, list):
        raise TypeError("OpenRouter rerank response is missing results")
    for row in results:
        if not isinstance(row, dict) or not isinstance(row.get("index"), int):
            raise TypeError("OpenRouter rerank response contains an invalid result")
        if not 0 <= row["index"] < len(documents):
            raise ValueError(
                "OpenRouter rerank response returned an invalid document index"
            )
    return results, body.get("usage")
