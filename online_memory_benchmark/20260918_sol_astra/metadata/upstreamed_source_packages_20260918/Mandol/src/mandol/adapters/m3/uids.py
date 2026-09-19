"""Deterministic identifiers and M3 memory-space names."""

from __future__ import annotations


def memory_uid(video_id: str, clip_id: int, memory_type: str, m3_node_id: str) -> str:
    if memory_type not in {"episodic", "semantic"}:
        raise ValueError(f"Unsupported M3 memory type: {memory_type}")
    return f"m3:{video_id}:clip:{clip_id}:{memory_type}:{m3_node_id}"


def relation_uid(video_id: str, clip_id: int, ordinal: int) -> str:
    return f"m3:{video_id}:clip:{clip_id}:relation:{ordinal}"


def entity_uid(video_id: str, canonical_entity_id: str) -> str:
    return f"m3:{video_id}:entity:{canonical_entity_id}"


def video_space(video_id: str) -> str:
    return f"m3:video:{video_id}"


def block_space(video_id: str, block_id: int) -> str:
    return f"m3:video:{video_id}:block:{block_id}"


def clip_space(video_id: str, clip_id: int) -> str:
    return f"m3:video:{video_id}:clip:{clip_id}"


SEMANTIC_SPACE = "m3:type:semantic"
