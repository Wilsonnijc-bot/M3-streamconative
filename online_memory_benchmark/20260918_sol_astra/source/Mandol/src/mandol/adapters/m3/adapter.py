"""Build a persisted Mandol graph from an M3 interchange directory."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any

from ...core.memory_space_registry import MemorySpaceRegistry, TowerSpace
from ...core.memory_unit import MemoryUnit
from ...core.semantic_graph import SemanticGraph
from ...core.semantic_map import SemanticMap
from ...retrieval.retrieval_interface import RetrievalMethod
from .embedding import (
    DEFAULT_BASE_URL,
    DEFAULT_DIMENSION,
    DEFAULT_MODEL,
    OpenAICompatible302EmbeddingAdapter,
    resolve_302_api_key,
)
from .relations import M3RelationBuilder, ValidatedRelation
from .schema import Interchange, load_interchange
from .uids import (
    SEMANTIC_SPACE,
    block_space,
    clip_space,
    entity_uid,
    memory_uid,
    relation_uid,
    video_space,
)


@dataclass
class M3MandolConfig:
    embedding_model: str = DEFAULT_MODEL
    embedding_dimension: int = DEFAULT_DIMENSION
    embedding_base_url: str = field(
        default_factory=lambda: os.getenv("API_302_BASE_URL", DEFAULT_BASE_URL)
    )
    embedding_batch_size: int = 32
    embedding_max_retries: int = 2
    embedding_timeout_seconds: float = 60.0
    relation_model: str = field(
        default_factory=lambda: os.getenv(
            "M3_MANDOL_RELATION_MODEL", "gemini-3.8-flash-302"
        )
    )
    relation_base_url: str = field(
        default_factory=lambda: os.getenv("API_302_BASE_URL", "https://api.302.ai/v1")
    )
    relation_max_retries: int = 2
    relation_timeout_seconds: float = 60.0
    build_relations: bool = True
    generate_sparse_embeddings: bool = True
    overwrite: bool = False
    api_key: str | None = field(default=None, repr=False)
    embedding_client: Any | None = field(default=None, repr=False)
    relation_client: Any | None = field(default=None, repr=False)

    def public_dict(self) -> dict[str, Any]:
        excluded = {"api_key", "embedding_client", "relation_client"}
        return {
            item.name: getattr(self, item.name)
            for item in fields(self)
            if item.name not in excluded
        }


class M3MandolAdapter:
    @classmethod
    def build(
        cls,
        input_dir: str | os.PathLike[str],
        output_dir: str | os.PathLike[str],
        config: M3MandolConfig | dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        config = cls._coerce_config(config)
        interchange = load_interchange(input_dir)
        output = Path(output_dir).expanduser().resolve()
        if output.exists() and any(output.iterdir()) and not config.overwrite:
            raise FileExistsError(f"Output directory is not empty: {output}")

        embedding_api_key = (
            resolve_302_api_key(config.api_key)
            if config.embedding_client is None
            else None
        )
        relation_api_key = (
            resolve_302_api_key(config.api_key)
            if config.build_relations and config.relation_client is None
            else None
        )
        embedding_adapter = OpenAICompatible302EmbeddingAdapter(
            api_key=embedding_api_key,
            base_url=config.embedding_base_url,
            model=config.embedding_model,
            expected_dimension=config.embedding_dimension,
            max_retries=config.embedding_max_retries,
            timeout_seconds=config.embedding_timeout_seconds,
            client=config.embedding_client,
        )
        semantic_map = SemanticMap(
            embedding_model_name=config.embedding_model,
            embedding_dim=config.embedding_dimension,
            embedding_adapter=embedding_adapter,
        )
        graph = SemanticGraph(semantic_map_instance=semantic_map)
        cls._create_spaces(graph, interchange)

        people_units = cls._person_units(interchange)
        cls._insert_batch(
            graph,
            people_units,
            [[TowerSpace.GRAPH_ENTITIES.value] for _ in people_units],
            config,
            generate_sparse=False,
        )

        direct_units, direct_spaces, uid_by_m3_node = cls._direct_memory_units(
            interchange
        )
        cls._insert_batch(
            graph,
            direct_units,
            direct_spaces,
            config,
            generate_sparse=config.generate_sparse_embeddings,
        )
        cls._add_memory_mentions(graph, interchange, uid_by_m3_node)

        relation_units: list[MemoryUnit] = []
        relation_spaces: list[list[str]] = []
        new_entity_units: dict[str, MemoryUnit] = {}
        relation_edges: list[tuple[str, str, str, dict[str, Any]]] = []
        relation_calls = 0
        if config.build_relations:
            relation_builder = M3RelationBuilder(
                llm_client=config.relation_client,
                model_name=config.relation_model,
                api_key=relation_api_key,
                base_url=config.relation_base_url,
                request_max_retries=config.relation_max_retries,
                request_timeout=config.relation_timeout_seconds,
            )
            (
                relation_units,
                relation_spaces,
                new_entity_units,
                relation_edges,
                relation_calls,
            ) = cls._build_relations(interchange, relation_builder, direct_units)

        cls._insert_batch(
            graph,
            list(new_entity_units.values()),
            [[TowerSpace.GRAPH_ENTITIES.value] for _ in new_entity_units],
            config,
            generate_sparse=False,
        )
        cls._insert_batch(
            graph,
            relation_units,
            relation_spaces,
            config,
            generate_sparse=config.generate_sparse_embeddings,
        )
        for source, target, predicate, properties in relation_edges:
            if not graph.add_relationship(source, target, predicate, **properties):
                raise RuntimeError(
                    f"Failed to add graph edge {source} -[{predicate}]-> {target}"
                )

        graph.semantic_map.build_index()
        index_stats = graph.get_multi_retriever().build_all_indexes(
            methods_to_build=[RetrievalMethod.BM25, RetrievalMethod.SPLADE],
            force_rebuild=True,
        )
        if index_stats.get("failed_count"):
            raise RuntimeError(f"Mandol index rebuild failed: {index_stats['details']}")
        cls._assert_membership_invariants(graph, interchange.manifest.video_id)
        result = {
            "schema_version": interchange.manifest.schema_version,
            "video_id": interchange.manifest.video_id,
            "source_embedding": {
                "model": interchange.manifest.source_embedding_model,
                "dimension": interchange.manifest.source_embedding_dimension,
                "vectors_imported": False,
            },
            "mandol_embedding": {
                "provider": "302.ai",
                "base_url": config.embedding_base_url.rstrip("/"),
                "model": config.embedding_model,
                "dimension": config.embedding_dimension,
            },
            "counts": {
                "source_memories": len(direct_units),
                "entities": len(people_units) + len(new_entity_units),
                "relations": len(relation_units),
                "relation_llm_calls": relation_calls,
            },
            "index_build": index_stats,
            "config": config.public_dict(),
        }
        cls._save_atomically(graph, output, result, config.overwrite)
        return result

    @staticmethod
    def _coerce_config(
        config: M3MandolConfig | dict[str, Any] | None,
    ) -> M3MandolConfig:
        if config is None:
            return M3MandolConfig()
        if isinstance(config, M3MandolConfig):
            return config
        return M3MandolConfig(**config)

    @staticmethod
    def _create_spaces(graph: SemanticGraph, interchange: Interchange) -> None:
        MemorySpaceRegistry.initialize_spaces(graph)
        semantic_map = graph.semantic_map
        video_id = interchange.manifest.video_id
        root = video_space(video_id)
        semantic_map.create_memory_space(root)
        semantic_map.create_memory_space(SEMANTIC_SPACE)
        for block_id in sorted({memory.block_id for memory in interchange.memories}):
            block = block_space(video_id, block_id)
            semantic_map.create_memory_space(block)
            semantic_map.add_space_to_space(block, root)
        for clip_id in interchange.manifest.clip_ids:
            clip = clip_space(video_id, clip_id)
            semantic_map.create_memory_space(clip)
            semantic_map.add_space_to_space(clip, block_space(video_id, clip_id // 5))

    @staticmethod
    def _person_units(interchange: Interchange) -> list[MemoryUnit]:
        video_id = interchange.manifest.video_id
        return [
            MemoryUnit(
                uid=entity_uid(video_id, entity.canonical_entity_id),
                raw_data={
                    "text_content": f"M3 person {entity.canonical_entity_id} in video {video_id}",
                    "entity_id": entity.canonical_entity_id,
                    "entity_type": "person",
                },
                metadata={
                    "adapter": "m3-mandol/v1",
                    "retrieval_candidate": False,
                    "face_node_ids": entity.face_node_ids,
                    "voice_node_ids": entity.voice_node_ids,
                },
            )
            for entity in interchange.entities
        ]

    @staticmethod
    def _direct_memory_units(
        interchange: Interchange,
    ) -> tuple[list[MemoryUnit], list[list[str]], dict[str, str]]:
        video_id = interchange.manifest.video_id
        units: list[MemoryUnit] = []
        memberships: list[list[str]] = []
        uid_by_m3_node: dict[str, str] = {}
        for memory in interchange.memories:
            uid = memory_uid(
                video_id, memory.clip_id, memory.memory_type, memory.m3_node_id
            )
            uid_by_m3_node[memory.m3_node_id] = uid
            type_space = (
                TowerSpace.EPISODIC_ROOT.value
                if memory.memory_type == "episodic"
                else SEMANTIC_SPACE
            )
            spaces = [
                clip_space(video_id, memory.clip_id),
                block_space(video_id, memory.block_id),
                type_space,
            ]
            units.append(
                MemoryUnit(
                    uid=uid,
                    raw_data={"text_content": memory.text},
                    metadata={
                        "adapter": "m3-mandol/v1",
                        "retrieval_candidate": True,
                        "memory_type": memory.memory_type,
                        "m3_node_id": memory.m3_node_id,
                        "video_id": video_id,
                        "clip_id": memory.clip_id,
                        "block_id": memory.block_id,
                        "canonical_entity_ids": memory.canonical_entity_ids,
                        "provenance": memory.provenance.model_dump(),
                    },
                )
            )
            memberships.append(spaces)
        return units, memberships, uid_by_m3_node

    @staticmethod
    def _insert_batch(
        graph: SemanticGraph,
        units: list[MemoryUnit],
        memberships: list[list[str]],
        config: M3MandolConfig,
        generate_sparse: bool,
    ) -> None:
        if not units:
            return
        stats = graph.batch_add_units(
            units,
            batch_size=config.embedding_batch_size,
            explicit_contents_for_embedding=[
                unit.raw_data["text_content"] for unit in units
            ],
            content_types_for_embedding=["text"] * len(units),
            per_unit_space_names=memberships,
            index_update_mode="none",
            generate_sparse_embedding=generate_sparse,
            show_progress=False,
        )
        missing_dense = [unit.uid for unit in units if unit.embedding is None]
        if stats.get("embedding_generated") != len(units) or missing_dense:
            raise RuntimeError(
                f"Fail-closed embedding generation failed for {missing_dense or 'one or more units'}"
            )
        if generate_sparse:
            missing_sparse = [
                unit.uid for unit in units if unit.sparse_embedding is None
            ]
            if missing_sparse:
                raise RuntimeError(f"SPLADE generation failed for {missing_sparse}")

    @staticmethod
    def _add_memory_mentions(
        graph: SemanticGraph, interchange: Interchange, uid_by_m3_node: dict[str, str]
    ) -> None:
        video_id = interchange.manifest.video_id
        for memory in interchange.memories:
            source = uid_by_m3_node[memory.m3_node_id]
            for canonical_id in memory.canonical_entity_ids:
                graph.add_relationship(
                    source,
                    entity_uid(video_id, canonical_id),
                    "mentions_entity",
                    evidence_source="m3",
                )

    @classmethod
    def _build_relations(
        cls,
        interchange: Interchange,
        relation_builder: M3RelationBuilder,
        direct_units: list[MemoryUnit],
    ) -> tuple[
        list[MemoryUnit],
        list[list[str]],
        dict[str, MemoryUnit],
        list[tuple[str, str, str, dict[str, Any]]],
        int,
    ]:
        video_id = interchange.manifest.video_id
        known_people = {entity.canonical_entity_id for entity in interchange.entities}
        units_by_clip: dict[int, list[MemoryUnit]] = {}
        for unit in direct_units:
            units_by_clip.setdefault(int(unit.metadata["clip_id"]), []).append(unit)

        relation_units: list[MemoryUnit] = []
        relation_spaces: list[list[str]] = []
        new_entities: dict[str, MemoryUnit] = {}
        edges: list[tuple[str, str, str, dict[str, Any]]] = []
        calls = 0
        for clip_id in sorted(units_by_clip):
            evidence_units = units_by_clip[clip_id]
            payloads = [
                {
                    "uid": unit.uid,
                    "type": unit.metadata["memory_type"],
                    "text": unit.raw_data["text_content"],
                }
                for unit in evidence_units
            ]
            generated_entities, relations = relation_builder.build_clip(
                clip_id, payloads, known_people
            )
            calls += 1
            for canonical_id, entity_type in generated_entities.items():
                if entity_type == "person" or canonical_id in new_entities:
                    continue
                new_entities[canonical_id] = MemoryUnit(
                    uid=entity_uid(video_id, canonical_id),
                    raw_data={
                        "text_content": f"M3 {entity_type} {canonical_id} in video {video_id}",
                        "entity_id": canonical_id,
                        "entity_type": entity_type,
                    },
                    metadata={
                        "adapter": "m3-mandol/v1",
                        "retrieval_candidate": False,
                        "generated_by": "relation_extraction",
                    },
                )
            for ordinal, relation in enumerate(relations):
                uid = relation_uid(video_id, clip_id, ordinal)
                relation_units.append(cls._relation_unit(uid, video_id, relation))
                relation_spaces.append(
                    [
                        clip_space(video_id, clip_id),
                        block_space(video_id, clip_id // 5),
                        TowerSpace.GRAPH_RELATIONS.value,
                    ]
                )
                subject_uid = entity_uid(video_id, relation.subject)
                object_uid = entity_uid(video_id, relation.object)
                edges.append(
                    (
                        subject_uid,
                        object_uid,
                        relation.predicate,
                        {"relation_uid": uid, "clip_id": clip_id},
                    )
                )
                participants = [subject_uid, object_uid]
                if relation.target:
                    target_uid = entity_uid(video_id, relation.target)
                    edges.append(
                        (
                            object_uid,
                            target_uid,
                            relation.target_predicate or f"{relation.predicate}_to",
                            {"relation_uid": uid, "clip_id": clip_id},
                        )
                    )
                    participants.append(target_uid)
                for participant_uid in participants:
                    edges.append(
                        (uid, participant_uid, "mentions_entity", {"clip_id": clip_id})
                    )
                for evidence_uid in relation.evidence:
                    edges.append(
                        (uid, evidence_uid, "supported_by", {"clip_id": clip_id})
                    )
        return relation_units, relation_spaces, new_entities, edges, calls

    @staticmethod
    def _relation_unit(
        uid: str, video_id: str, relation: ValidatedRelation
    ) -> MemoryUnit:
        return MemoryUnit(
            uid=uid,
            raw_data={"text_content": relation.text},
            metadata={
                "adapter": "m3-mandol/v1",
                "retrieval_candidate": True,
                "memory_type": "relation",
                "video_id": video_id,
                "clip_id": relation.clip_id,
                "block_id": relation.clip_id // 5,
                "subject": relation.subject,
                "predicate": relation.predicate,
                "object": relation.object,
                "target": relation.target,
                "target_predicate": relation.target_predicate,
                "evidence_uids": list(relation.evidence),
                "provenance": {
                    "source": "302.ai relation extraction",
                    "evidence_uids": list(relation.evidence),
                },
            },
        )

    @staticmethod
    def _assert_membership_invariants(graph: SemanticGraph, video_id: str) -> None:
        searchable_types = {
            TowerSpace.EPISODIC_ROOT.value,
            SEMANTIC_SPACE,
            TowerSpace.GRAPH_RELATIONS.value,
        }
        for unit in graph.get_all_units():
            direct_spaces = {
                name
                for name, space in graph.semantic_map.memory_spaces.items()
                if space.contains_unit(unit.uid, recursive=False)
            }
            if unit.metadata.get("retrieval_candidate"):
                clip_spaces = {
                    name
                    for name in direct_spaces
                    if name.startswith(f"m3:video:{video_id}:clip:")
                }
                block_spaces = {
                    name
                    for name in direct_spaces
                    if name.startswith(f"m3:video:{video_id}:block:")
                }
                type_spaces = direct_spaces & searchable_types
                if (
                    len(clip_spaces) != 1
                    or len(block_spaces) != 1
                    or len(type_spaces) != 1
                    or len(direct_spaces) != 3
                ):
                    raise RuntimeError(
                        f"Invalid direct space membership for {unit.uid}: {sorted(direct_spaces)}"
                    )
            elif direct_spaces != {TowerSpace.GRAPH_ENTITIES.value}:
                raise RuntimeError(
                    f"Entity anchor {unit.uid} has invalid spaces: {sorted(direct_spaces)}"
                )

    @staticmethod
    def _save_atomically(
        graph: SemanticGraph,
        output: Path,
        build_manifest: dict[str, Any],
        overwrite: bool,
    ) -> None:
        output.parent.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=output.parent))
        try:
            graph.save_graph(
                str(staging),
                freeze_retrievers=False,
                force_rebuild_retrievers=False,
                retriever_methods_to_build=[
                    RetrievalMethod.BM25,
                    RetrievalMethod.SPLADE,
                ],
                build_sparse_vectors=False,
            )
            (staging / "m3_adapter_manifest.json").write_text(
                json.dumps(build_manifest, indent=2) + "\n", encoding="utf-8"
            )
            if output.exists():
                if not overwrite and any(output.iterdir()):
                    raise FileExistsError(f"Output directory is not empty: {output}")
                shutil.rmtree(output)
            os.replace(staging, output)
        finally:
            if staging.exists():
                shutil.rmtree(staging)
