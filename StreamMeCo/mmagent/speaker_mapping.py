"""Native online speaker assignment shared by all speaker encoders."""

from __future__ import annotations

from typing import Any

import numpy as np


def score_candidates(graph, embeddings) -> list[dict[str, Any]]:
    """Score every existing voice node before the graph is mutated."""
    query = np.asarray(embeddings, dtype=float)
    query = query.reshape(-1, query.shape[-1])
    query = query / np.maximum(np.linalg.norm(query, axis=1, keepdims=True), 1e-30)
    candidates = []
    for node_id, node in graph.nodes.items():
        if node.type != "voice":
            continue
        vectors = np.asarray(node.embeddings, dtype=float).reshape(-1, query.shape[-1])
        vectors = vectors / np.maximum(
            np.linalg.norm(vectors, axis=1, keepdims=True), 1e-30
        )
        score = float(np.mean(query @ vectors.T))
        eligible = score >= graph.audio_matching_threshold
        candidates.append(
            {
                "candidate_id": f"voice_{node_id}",
                "score": score,
                "eligible": eligible,
                "rejection_reason": None if eligible else "below_threshold",
            }
        )
    return candidates


def assign_voice(
    graph,
    embeddings,
    transcript: str,
    *,
    method: str,
    method_id: str | None = None,
    details: dict[str, Any] | None = None,
):
    """Apply M3's native match/update/create policy and return its evidence."""
    audio_info = {"embeddings": list(embeddings), "contents": [transcript]}
    candidates = score_candidates(graph, audio_info["embeddings"])
    matched_nodes = graph.search_voice_nodes(audio_info)
    if matched_nodes:
        node_id = matched_nodes[0][0]
        graph.update_node(node_id, audio_info)
        created = False
    else:
        node_id = graph.add_voice_node(audio_info)
        created = True

    candidate_scores = {
        candidate["candidate_id"]: candidate["score"] for candidate in candidates
    }
    result = {
        "method": method,
        "method_id": method_id or method,
        "candidates": candidates,
        "candidate_scores": candidate_scores,
        "best_score": max(candidate_scores.values()) if candidate_scores else None,
        "threshold": graph.audio_matching_threshold,
        "predicted_identity": f"voice_{node_id}",
        "created_new_identity": created,
        "retained_embeddings": len(graph.nodes[node_id].embeddings),
        "enrollment_policy": "online_native_m3",
    }
    if details:
        result.update(details)
    return node_id, result
