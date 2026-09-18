"""Scoped hybrid retrieval for persisted M3 Mandol graphs."""

from __future__ import annotations

import json
import shutil
import tempfile
import threading
from pathlib import Path
from typing import Any

from ...core.memory_space_registry import TowerSpace
from ...core.semantic_graph import SemanticGraph
from ...retrieval.retrieval_interface import RetrievalMethod
from .embedding import OpenAICompatible302EmbeddingAdapter, resolve_302_api_key
from .uids import SEMANTIC_SPACE, block_space, clip_space, video_space
from .publication import current_version, resolve_bundle


class M3MandolRetriever:
    def __init__(self, graph: SemanticGraph, build_manifest: dict[str, Any]):
        self.graph = graph
        self.build_manifest = build_manifest
        self.video_id = build_manifest["video_id"]
        self._publication_root = None
        self._reload_lock = threading.Lock()
        self._active_retriever = None

    @classmethod
    def load(
        cls,
        graph_dir: str | Path,
        api_key: str | None = None,
        embedding_base_url: str | None = None,
        embedding_model: str | None = None,
        embedding_dimension: int | None = None,
        embedding_client: Any | None = None,
    ) -> M3MandolRetriever:
        root = Path(graph_dir).expanduser().resolve()
        publication_root = root if (root/'CURRENT.json').is_file() else None
        loaded_version = None
        if publication_root:
            loaded_version, root = resolve_bundle(root)
        elif (root/'retrieval_ready.json').is_file():
            root = root/'mandol'
        runtime_directory = None
        if (root.parent/'retrieval_ready.json').is_file():
            # Some storage/index loaders write caches and locks. Keep immutable
            # publication bytes intact, even while an older query is finishing.
            runtime_directory = tempfile.TemporaryDirectory(prefix='mandol-retrieval-')
            runtime_root = Path(runtime_directory.name)/'graph'
            shutil.copytree(root, runtime_root)
            root = runtime_root
        manifest_path = root / "m3_adapter_manifest.json"
        if not manifest_path.is_file():
            raise FileNotFoundError(f"Missing M3 adapter manifest: {manifest_path}")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        saved = manifest["mandol_embedding"]
        requested = {
            "base_url": (embedding_base_url or saved["base_url"]).rstrip("/"),
            "model": embedding_model or saved["model"],
            "dimension": embedding_dimension or saved["dimension"],
        }
        expected = {
            "base_url": saved["base_url"].rstrip("/"),
            "model": saved["model"],
            "dimension": saved["dimension"],
        }
        if requested != expected:
            raise ValueError(
                f"Embedding configuration differs from the saved graph: expected {expected}"
            )
        adapter = OpenAICompatible302EmbeddingAdapter(
            api_key=None
            if embedding_client is not None
            else resolve_302_api_key(api_key),
            base_url=requested["base_url"],
            model=requested["model"],
            expected_dimension=requested["dimension"],
            client=embedding_client,
        )
        graph = SemanticGraph.load_graph(str(root), embedding_adapter=adapter)
        result = cls(graph, manifest)
        result._runtime_directory = runtime_directory
        result._publication_root = publication_root
        result._loaded_version = loaded_version
        result._reload_options = dict(api_key=api_key, embedding_base_url=embedding_base_url,
            embedding_model=embedding_model, embedding_dimension=embedding_dimension,
            embedding_client=embedding_client)
        return result

    def search(
        self,
        query: str,
        top_k: int = 10,
        scope: str | dict[str, Any] | None = None,
        enable_graph_expansion: bool = False,
        rerank_method: str | None = None,
    ) -> list[dict[str, Any]]:
        if self._publication_root is not None:
            with self._reload_lock:
                version = current_version(self._publication_root)
                if version != self._loaded_version:
                    candidate = type(self).load(self._publication_root, **self._reload_options)
                    candidate._publication_root = None  # Pin this object for in-flight queries.
                    self._active_retriever = candidate
                    self._loaded_version = candidate._loaded_version
                active = self._active_retriever or self
            if active is not self:
                return active.search(query, top_k=top_k, scope=scope,
                    enable_graph_expansion=enable_graph_expansion, rerank_method=rerank_method)
        if not query.strip() or top_k <= 0:
            raise ValueError("query must be non-empty and top_k must be positive")
        candidate_uids = self._candidate_uids(scope)
        if not candidate_uids:
            return []
        detailed = self.graph.get_multi_retriever().smart_search(
            query,
            methods=[
                RetrievalMethod.BM25,
                RetrievalMethod.COSINE_SIMILARITY,
                RetrievalMethod.SPLADE,
            ],
            top_k=max(top_k, min(len(candidate_uids), top_k * 3)),
            fusion_method="rrf",
            rerank_method=rerank_method,
            enable_graph_expansion=enable_graph_expansion,
            candidate_uids=sorted(candidate_uids),
            return_detailed=True,
        )
        ranked = detailed.get("results", []) if isinstance(detailed, dict) else detailed
        output: list[dict[str, Any]] = []
        for unit, score in ranked:
            if unit.uid not in candidate_uids:
                continue
            item = {
                "uid": unit.uid,
                "score": float(score),
                "text": unit.raw_data.get("text_content", unit.text_cached),
                "raw_data": unit.raw_data,
                "metadata": unit.metadata,
                "provenance": unit.metadata.get("provenance"),
                "spaces": sorted(self._direct_spaces(unit.uid)),
            }
            if enable_graph_expansion:
                item["graph_context"] = self._graph_context(unit.uid)
            output.append(item)
            if len(output) >= top_k:
                break
        return output

    def _candidate_uids(self, scope: str | dict[str, Any] | None) -> set[str]:
        type_spaces = [
            TowerSpace.EPISODIC_ROOT.value,
            SEMANTIC_SPACE,
            TowerSpace.GRAPH_RELATIONS.value,
        ]
        candidates = {
            unit.uid
            for unit in self.graph.get_units_in_memory_space(
                type_spaces, recursive=False
            )
            if unit.metadata.get("retrieval_candidate")
        }
        scope_space = self._scope_space(scope)
        if scope_space:
            scoped = {
                unit.uid
                for unit in self.graph.get_units_in_memory_space(
                    scope_space, recursive=True
                )
            }
            candidates &= scoped
        return candidates

    def _scope_space(self, scope: str | dict[str, Any] | None) -> str | None:
        if scope is None:
            return None
        if isinstance(scope, str):
            return scope
        if len(scope) != 1:
            raise ValueError("scope must contain exactly one of video, block, or clip")
        key, value = next(iter(scope.items()))
        if key == "video":
            if str(value) != self.video_id:
                raise ValueError(
                    f"This graph contains video {self.video_id}, not {value}"
                )
            return video_space(self.video_id)
        if key == "block":
            return block_space(self.video_id, int(value))
        if key == "clip":
            return clip_space(self.video_id, int(value))
        raise ValueError("scope must contain video, block, or clip")

    def _direct_spaces(self, uid: str) -> set[str]:
        return {
            name
            for name, space in self.graph.semantic_map.memory_spaces.items()
            if space.contains_unit(uid, recursive=False)
        }

    def _graph_context(self, uid: str) -> dict[str, Any]:
        neighbors = sorted(
            set(self.graph.get_successors(uid)) | set(self.graph.get_predecessors(uid))
        )
        return {
            "successors": self.graph.get_successors(uid),
            "predecessors": self.graph.get_predecessors(uid),
            "neighbors": [
                {
                    "uid": neighbor,
                    "text": unit.raw_data.get("text_content", unit.text_cached)
                    if (unit := self.graph.get_unit(neighbor))
                    else None,
                }
                for neighbor in neighbors
            ],
        }
