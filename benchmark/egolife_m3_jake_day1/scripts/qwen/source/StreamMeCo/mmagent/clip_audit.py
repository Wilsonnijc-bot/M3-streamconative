"""Readable per-clip memory and graph audit artifacts."""
import base64
import hashlib
import json
from collections import Counter
from pathlib import Path


def _content_view(node_type, value):
    if node_type != "img":
        return value
    if not isinstance(value, str):
        return value
    try:
        raw = base64.b64decode(value, validate=True)
    except Exception:
        return value
    return {
        "kind": "base64_face_image",
        "encoded_chars": len(value),
        "decoded_bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def node_view(node):
    embeddings = node.embeddings or []
    dimensions = []
    for embedding in embeddings:
        try:
            dimensions.append(len(embedding))
        except TypeError:
            dimensions.append(None)
    metadata = dict(node.metadata)
    metadata["contents"] = [
        _content_view(node.type, value)
        for value in metadata.get("contents", [])
    ]
    return {
        "id": node.id,
        "type": node.type,
        "metadata": metadata,
        "embedding_count": len(embeddings),
        "embedding_dimensions": dimensions,
    }


def edge_view(graph):
    edges = []
    for (source, target), weight in sorted(graph.edges.items()):
        if source >= target:
            continue
        edges.append({
            "source": source,
            "target": target,
            "weight": weight,
            "source_type": graph.nodes[source].type,
            "target_type": graph.nodes[target].type,
        })
    return edges


def graph_view(graph):
    nodes = [node_view(graph.nodes[node_id]) for node_id in sorted(graph.nodes)]
    edges = edge_view(graph)
    counts = Counter(node["type"] for node in nodes)
    return {
        "counts": {
            "nodes": len(nodes),
            "edges": len(edges),
            "directed_edges_stored": len(graph.edges),
            "by_type": dict(sorted(counts.items())),
        },
        "nodes": nodes,
        "edges": edges,
    }


def graph_identity(graph):
    return set(graph.nodes), set(graph.edges)


def graph_delta(graph, before_nodes, before_edges):
    added_nodes = sorted(set(graph.nodes) - set(before_nodes))
    added_directed_edges = set(graph.edges) - set(before_edges)
    added_edges = [
        edge for edge in edge_view(graph)
        if (edge["source"], edge["target"]) in added_directed_edges
        or (edge["target"], edge["source"]) in added_directed_edges
    ]
    return {
        "nodes_added": len(added_nodes),
        "edges_added": len(added_edges),
        "nodes": [node_view(graph.nodes[node_id]) for node_id in added_nodes],
        "edges": added_edges,
    }


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temp.replace(path)
