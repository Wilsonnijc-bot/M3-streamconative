from __future__ import annotations

import json
import pickle
from types import SimpleNamespace

import pytest
from m3_agent.export_mandol import SCHEMA_VERSION, export_graph


def _node(node_id, node_type, text=None, clip_id=None, embedding_dim=4):
    metadata = {"contents": [] if text is None else [text]}
    if clip_id is not None:
        metadata["timestamp"] = clip_id
    embeddings = [] if text is None else [[float(node_id + 1)] * embedding_dim]
    return SimpleNamespace(
        id=node_id, type=node_type, metadata=metadata, embeddings=embeddings
    )


def _write_graph(path, *, include_mapping=True):
    graph = SimpleNamespace(
        nodes={
            1: _node(1, "img"),
            2: _node(2, "voice"),
            10: _node(10, "episodic", "<face_1> greets <character_0>", 0),
            11: _node(11, "semantic", "<voice_2> is speaking", 7),
            12: _node(12, "semantic", "Equivalence: <face_1> is <voice_2>", 7),
        },
        edges={(10, 1): 1.0, (1, 10): 1.0},
    )
    if include_mapping:
        graph.character_mappings = {"character_0": ["face_1", "voice_2"]}
        graph.reverse_character_mappings = {
            "face_1": "character_0",
            "voice_2": "character_0",
        }
    with path.open("wb") as handle:
        pickle.dump(graph, handle)


@pytest.mark.parametrize("compressed", [False, True])
def test_export_contract_is_embedding_free(tmp_path, compressed):
    graph_path = tmp_path / "graph.pkl"
    output = tmp_path / "export"
    _write_graph(graph_path)

    manifest = export_graph(graph_path, output, "video-1", compressed=compressed)

    assert manifest.schema_version == SCHEMA_VERSION
    assert manifest.compressed is compressed
    assert manifest.clip_ids == [0, 7]
    assert manifest.source_embedding_dimension == 4
    records = [
        json.loads(line)
        for line in (output / "memories.jsonl").read_text().splitlines()
    ]
    assert len(records) == 2
    assert records[1]["block_id"] == 1
    assert records[1]["provenance"]["start_time_seconds"] == 210.0
    assert all("embeddings" not in record for record in records)
    entities = [
        json.loads(line)
        for line in (output / "entities.jsonl").read_text().splitlines()
    ]
    assert entities == [
        {
            "schema_version": SCHEMA_VERSION,
            "canonical_entity_id": "character_0",
            "face_node_ids": [1],
            "voice_node_ids": [2],
        }
    ]


def test_export_rejects_unmapped_face_reference(tmp_path):
    graph_path = tmp_path / "graph.pkl"
    _write_graph(graph_path, include_mapping=False)
    with pytest.raises(ValueError, match="unmapped media entities"):
        export_graph(graph_path, tmp_path / "export", "video-1")


def test_export_accepts_empty_graph(tmp_path):
    graph_path = tmp_path / "empty.pkl"
    with graph_path.open("wb") as handle:
        pickle.dump(
            SimpleNamespace(
                nodes={}, edges={}, character_mappings={}, reverse_character_mappings={}
            ),
            handle,
        )
    manifest = export_graph(graph_path, tmp_path / "export", "empty")
    assert manifest.memory_count == 0
    assert manifest.entity_count == 0
    assert manifest.clip_ids == []
