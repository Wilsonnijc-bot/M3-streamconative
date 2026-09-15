"""Export an M3 VideoGraph to the neutral Mandol interchange contract."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pickle
import re
import sys
import tempfile
from collections.abc import Iterable
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

SCHEMA_VERSION = "m3-mandol/v1"
SOURCE_EMBEDDING_MODEL = "text-embedding-3-large"
ENTITY_PATTERN = re.compile(
    r"<(?P<kind>face|voice|character)_(?P<id>\d+)>", re.IGNORECASE
)


class ExportManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[SCHEMA_VERSION] = SCHEMA_VERSION
    video_id: str = Field(min_length=1)
    clip_duration_seconds: float = Field(default=30.0, gt=0)
    clips_per_block: int = Field(default=5, gt=0)
    compressed: bool
    source_graph_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_embedding_model: str = SOURCE_EMBEDDING_MODEL
    source_embedding_dimension: int | None = Field(default=None, gt=0)
    memory_count: int = Field(ge=0)
    entity_count: int = Field(ge=0)
    clip_ids: list[int]

    @field_validator("video_id")
    @classmethod
    def validate_video_id(cls, value: str) -> str:
        value = value.strip()
        if not re.fullmatch(r"[A-Za-z0-9._-]+", value):
            raise ValueError(
                "video_id may contain only letters, digits, '.', '_', and '-'"
            )
        return value


class MemoryProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: Literal["StreamMeCo/M3"] = "StreamMeCo/M3"
    source_node_id: str
    source_embedding_model: str = SOURCE_EMBEDDING_MODEL
    source_embedding_dimension: int | None = Field(default=None, gt=0)
    start_time_seconds: float = Field(ge=0)
    end_time_seconds: float = Field(gt=0)


class MemoryRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[SCHEMA_VERSION] = SCHEMA_VERSION
    m3_node_id: str = Field(min_length=1)
    memory_type: Literal["episodic", "semantic"]
    clip_id: int = Field(ge=0)
    block_id: int = Field(ge=0)
    text: str = Field(min_length=1)
    canonical_entity_ids: list[str]
    provenance: MemoryProvenance


class EntityRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[SCHEMA_VERSION] = SCHEMA_VERSION
    canonical_entity_id: str = Field(pattern=r"^character_\d+$")
    face_node_ids: list[int]
    voice_node_ids: list[int]


@contextmanager
def _working_directory(path: Path):
    previous = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


def _load_graph(path: Path) -> Any:
    """Load current and legacy pickles without eagerly importing M3."""
    try:
        with path.open("rb") as handle:
            return pickle.load(handle)
    except (ModuleNotFoundError, ImportError, FileNotFoundError):
        project_root = Path(__file__).resolve().parents[1]
        with _working_directory(project_root):
            from mmagent import videograph as videograph_module

        sys.modules.setdefault("videograph", videograph_module)
        with path.open("rb") as handle:
            return pickle.load(handle)


def _source_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _text_from_node(node: Any) -> str:
    contents = getattr(node, "metadata", {}).get("contents", [])
    if isinstance(contents, str):
        return contents.strip()
    if isinstance(contents, Iterable):
        return "\n".join(
            str(item).strip() for item in contents if str(item).strip()
        ).strip()
    return ""


def _infer_embedding_dimension(graph: Any) -> int | None:
    for node in getattr(graph, "nodes", {}).values():
        if getattr(node, "type", None) not in {"episodic", "semantic"}:
            continue
        embeddings = getattr(node, "embeddings", None) or []
        if not embeddings:
            continue
        try:
            dimension = len(embeddings[0])
        except TypeError:
            continue
        if dimension > 0:
            return dimension
    return None


def _refresh_character_mappings(graph: Any) -> None:
    if hasattr(graph, "character_mappings") and hasattr(
        graph, "reverse_character_mappings"
    ):
        return
    refresh = getattr(graph, "refresh_equivalences", None)
    if callable(refresh):
        refresh()


def _build_entity_records(graph: Any) -> tuple[list[EntityRecord], dict[str, str]]:
    _refresh_character_mappings(graph)
    mappings = dict(getattr(graph, "character_mappings", {}) or {})
    reverse = dict(getattr(graph, "reverse_character_mappings", {}) or {})

    for node in getattr(graph, "nodes", {}).values():
        if getattr(node, "type", None) not in {"episodic", "semantic"}:
            continue
        for match in ENTITY_PATTERN.finditer(_text_from_node(node)):
            tag = f"{match.group('kind').lower()}_{int(match.group('id'))}"
            if tag.startswith("character_"):
                mappings.setdefault(tag, [])

    records: list[EntityRecord] = []
    for character_id in sorted(
        mappings, key=lambda value: int(value.rsplit("_", 1)[1])
    ):
        face_ids: set[int] = set()
        voice_ids: set[int] = set()
        for raw_tag in mappings[character_id]:
            tag = str(raw_tag).lower()
            match = re.fullmatch(r"(face|voice)_(\d+)", tag)
            if not match:
                continue
            node_id = int(match.group(2))
            if match.group(1) == "face":
                face_ids.add(node_id)
            else:
                voice_ids.add(node_id)
            reverse[tag] = character_id
        records.append(
            EntityRecord(
                canonical_entity_id=character_id,
                face_node_ids=sorted(face_ids),
                voice_node_ids=sorted(voice_ids),
            )
        )
    return records, reverse


def _entities_for_memory(
    graph: Any, node_id: Any, text: str, reverse: dict[str, str]
) -> list[str]:
    result: set[str] = set()
    unresolved: set[str] = set()
    for match in ENTITY_PATTERN.finditer(text):
        tag = f"{match.group('kind').lower()}_{int(match.group('id'))}"
        canonical = tag if tag.startswith("character_") else reverse.get(tag)
        if canonical:
            result.add(canonical)
        elif not tag.startswith("character_"):
            unresolved.add(tag)

    for left, right in getattr(graph, "edges", {}):
        adjacent = right if left == node_id else left if right == node_id else None
        if adjacent is None:
            continue
        adjacent_node = getattr(graph, "nodes", {}).get(adjacent)
        node_type = getattr(adjacent_node, "type", None)
        if node_type not in {"img", "voice"}:
            continue
        prefix = "face" if node_type == "img" else "voice"
        canonical = reverse.get(f"{prefix}_{adjacent}")
        if canonical:
            result.add(canonical)

    if unresolved:
        raise ValueError(
            f"M3 node {node_id} references unmapped media entities: {sorted(unresolved)}"
        )

    return sorted(result, key=lambda value: int(value.rsplit("_", 1)[1]))


def export_graph(
    input_graph: str | os.PathLike[str],
    output_dir: str | os.PathLike[str],
    video_id: str,
    clip_duration_seconds: float = 30.0,
    compressed: bool = False,
) -> ExportManifest:
    input_path = Path(input_graph).expanduser().resolve()
    if not input_path.is_file():
        raise FileNotFoundError(f"M3 graph does not exist: {input_path}")

    graph = _load_graph(input_path)
    embedding_dimension = _infer_embedding_dimension(graph)
    entities, reverse = _build_entity_records(graph)
    known_entities = {record.canonical_entity_id for record in entities}

    memories: list[MemoryRecord] = []
    for node_id in sorted(getattr(graph, "nodes", {}), key=lambda value: str(value)):
        node = graph.nodes[node_id]
        memory_type = getattr(node, "type", None)
        if memory_type not in {"episodic", "semantic"}:
            continue
        text = _text_from_node(node)
        if not text or (
            memory_type == "semantic" and text.lower().startswith("equivalence")
        ):
            continue
        clip_id = int(getattr(node, "metadata", {}).get("timestamp"))
        if clip_id < 0:
            raise ValueError(f"M3 node {node_id} has a negative clip ID")
        entity_ids = _entities_for_memory(graph, node_id, text, reverse)
        missing_entities = set(entity_ids) - known_entities
        if missing_entities:
            raise ValueError(
                f"M3 node {node_id} references unmapped entities: {sorted(missing_entities)}"
            )
        start = clip_id * clip_duration_seconds
        memories.append(
            MemoryRecord(
                m3_node_id=str(node_id),
                memory_type=memory_type,
                clip_id=clip_id,
                block_id=clip_id // 5,
                text=text,
                canonical_entity_ids=entity_ids,
                provenance=MemoryProvenance(
                    source_node_id=str(node_id),
                    source_embedding_dimension=embedding_dimension,
                    start_time_seconds=start,
                    end_time_seconds=start + clip_duration_seconds,
                ),
            )
        )

    memories.sort(key=lambda item: (item.clip_id, item.memory_type, item.m3_node_id))
    manifest = ExportManifest(
        video_id=video_id,
        clip_duration_seconds=clip_duration_seconds,
        compressed=compressed,
        source_graph_sha256=_source_sha256(input_path),
        source_embedding_dimension=embedding_dimension,
        memory_count=len(memories),
        entity_count=len(entities),
        clip_ids=sorted({item.clip_id for item in memories}),
    )

    destination = Path(output_dir).expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=f".{destination.name}.", dir=destination.parent
    ) as temp_name:
        temp_dir = Path(temp_name)
        (temp_dir / "manifest.json").write_text(
            manifest.model_dump_json(indent=2) + "\n", encoding="utf-8"
        )
        for name, records in (
            ("memories.jsonl", memories),
            ("entities.jsonl", entities),
        ):
            with (temp_dir / name).open("w", encoding="utf-8") as handle:
                for record in records:
                    handle.write(record.model_dump_json() + "\n")
        if destination.exists():
            if any(destination.iterdir()):
                raise FileExistsError(f"Output directory is not empty: {destination}")
            destination.rmdir()
        os.replace(temp_dir, destination)
    return manifest


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_graph", help="Path to an M3 VideoGraph pickle")
    parser.add_argument("output_dir", help="New interchange output directory")
    parser.add_argument("--video-id", required=True)
    parser.add_argument(
        "--clip-duration", type=float, default=30.0, dest="clip_duration_seconds"
    )
    parser.add_argument(
        "--compressed", action=argparse.BooleanOptionalAction, default=False
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    manifest = export_graph(**vars(args))
    print(json.dumps(manifest.model_dump(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
