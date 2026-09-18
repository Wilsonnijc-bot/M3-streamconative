"""Pydantic models and validation for the M3 interchange contract."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

SCHEMA_VERSION = "m3-mandol/v1"


class Manifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[SCHEMA_VERSION]
    video_id: str = Field(min_length=1)
    clip_duration_seconds: float = Field(gt=0)
    clips_per_block: Literal[5]
    compressed: bool
    source_graph_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_embedding_model: str = Field(min_length=1)
    source_embedding_dimension: int | None = Field(default=None, gt=0)
    memory_count: int = Field(ge=0)
    entity_count: int = Field(ge=0)
    clip_ids: list[int]

    @field_validator("video_id")
    @classmethod
    def validate_video_id(cls, value: str) -> str:
        value = value.strip()
        if not re.fullmatch(r"[A-Za-z0-9._-]+", value):
            raise ValueError("invalid video_id")
        return value


class MemoryProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: Literal["StreamMeCo/M3"]
    source_node_id: str
    source_embedding_model: str
    source_embedding_dimension: int | None = Field(default=None, gt=0)
    start_time_seconds: float = Field(ge=0)
    end_time_seconds: float = Field(gt=0)


class MemoryRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[SCHEMA_VERSION]
    m3_node_id: str = Field(min_length=1)
    memory_type: Literal["episodic", "semantic"]
    clip_id: int = Field(ge=0)
    block_id: int = Field(ge=0)
    text: str = Field(min_length=1)
    canonical_entity_ids: list[str]
    provenance: MemoryProvenance


class EntityRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[SCHEMA_VERSION]
    canonical_entity_id: str = Field(pattern=r"^character_\d+$")
    face_node_ids: list[int]
    voice_node_ids: list[int]


class Interchange(BaseModel):
    manifest: Manifest
    memories: list[MemoryRecord]
    entities: list[EntityRecord]


def _read_jsonl(path: Path, model_type: type[BaseModel]) -> list[BaseModel]:
    records: list[BaseModel] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                records.append(model_type.model_validate_json(line))
            except Exception as exc:
                raise ValueError(
                    f"Invalid {path.name} record at line {line_number}: {exc}"
                ) from exc
    return records


def load_interchange(input_dir: str | Path) -> Interchange:
    root = Path(input_dir).expanduser().resolve()
    required = [
        root / "manifest.json",
        root / "memories.jsonl",
        root / "entities.jsonl",
    ]
    missing = [path.name for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Missing M3 interchange files: {', '.join(missing)}")

    manifest = Manifest.model_validate(
        json.loads(required[0].read_text(encoding="utf-8"))
    )
    memories = list(_read_jsonl(required[1], MemoryRecord))
    entities = list(_read_jsonl(required[2], EntityRecord))
    if manifest.memory_count != len(memories) or manifest.entity_count != len(entities):
        raise ValueError("Manifest record counts do not match JSONL contents")

    entity_ids = [item.canonical_entity_id for item in entities]
    if len(entity_ids) != len(set(entity_ids)):
        raise ValueError("Duplicate canonical entity IDs")
    known_entities = set(entity_ids)
    seen_memory_ids: set[str] = set()
    for memory in memories:
        if memory.m3_node_id in seen_memory_ids:
            raise ValueError(f"Duplicate M3 node ID: {memory.m3_node_id}")
        seen_memory_ids.add(memory.m3_node_id)
        if memory.block_id != memory.clip_id // manifest.clips_per_block:
            raise ValueError(f"Invalid block ID for M3 node {memory.m3_node_id}")
        expected_start = memory.clip_id * manifest.clip_duration_seconds
        if abs(memory.provenance.start_time_seconds - expected_start) > 1e-6:
            raise ValueError(f"Invalid start timestamp for M3 node {memory.m3_node_id}")
        if (
            abs(
                memory.provenance.end_time_seconds
                - (expected_start + manifest.clip_duration_seconds)
            )
            > 1e-6
        ):
            raise ValueError(f"Invalid end timestamp for M3 node {memory.m3_node_id}")
        unknown = set(memory.canonical_entity_ids) - known_entities
        if unknown:
            raise ValueError(
                f"M3 node {memory.m3_node_id} references unknown entities: {sorted(unknown)}"
            )
    if sorted(set(manifest.clip_ids)) != sorted({item.clip_id for item in memories}):
        raise ValueError("Manifest clip_ids do not match memory records")
    return Interchange(manifest=manifest, memories=memories, entities=entities)
