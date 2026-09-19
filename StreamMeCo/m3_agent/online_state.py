"""Durable graph transactions and immutable online query snapshots."""

import hashlib
import json
import os
from pathlib import Path
import pickle
import shutil


def graph_bytes(graph):
    return pickle.dumps(graph, protocol=pickle.HIGHEST_PROTOCOL)


def file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic(path, value, binary=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    payload = (
        value
        if binary
        else (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode()
    )
    with temporary.open("wb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    descriptor = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


class GraphCheckpointStore:
    def __init__(self, root, methods, snapshot_interval_s=300):
        self.root = Path(root)
        self.methods = tuple(methods)
        self.snapshot_interval_us = round(snapshot_interval_s * 1_000_000)

    def periodic_path(self, method, cutoff):
        return (
            self.root
            / method
            / "graph_snapshots"
            / f"t_{cutoff:012.6f}"
            / "graph.pkl"
        )

    def checkpoint(
        self,
        graphs,
        event_index,
        source_fingerprint,
        plan_hash,
        *,
        phase="complete",
        media_timestamp=None,
    ):
        if set(graphs) != set(self.methods):
            raise ValueError("checkpoint graph set does not match configured methods")
        periodic = (
            media_timestamp is not None
            and round(media_timestamp * 1_000_000) % self.snapshot_interval_us == 0
            and phase != "observations_committed"
        )
        generation = self.root / "transactions" / f"event_{event_index:06d}_{phase}"
        files = {}
        for method, graph in graphs.items():
            path = (
                self.periodic_path(method, media_timestamp)
                if periodic
                else generation / method / "pending.pkl"
            )
            payload = graph_bytes(graph)
            expected = hashlib.sha256(payload).hexdigest()
            if path.exists():
                if file_sha256(path) != expected:
                    raise ValueError("checkpoint state changed within a timestamp")
            else:
                _atomic(path, payload, binary=True)
            files[method] = {
                "path": str(path.relative_to(self.root)),
                "sha256": expected,
            }
        current_path = self.root / "CURRENT.json"
        previous = json.loads(current_path.read_text()) if current_path.exists() else None
        state = {
            "event_index": event_index,
            "phase": phase,
            "media_timestamp": media_timestamp,
            "periodic": periodic,
            "generation": None
            if periodic
            else str(generation.relative_to(self.root)),
            "fingerprint": source_fingerprint,
            "plan_hash": plan_hash,
            "graphs": files,
        }
        _atomic(current_path, state)
        if (
            previous
            and not previous.get("periodic", False)
            and previous.get("generation")
            and previous["generation"] != state["generation"]
        ):
            old_generation = self.root / previous["generation"]
            if old_generation.is_dir():
                shutil.rmtree(old_generation)

    def finish(self, event_index):
        current_path = self.root / "CURRENT.json"
        if not current_path.exists():
            return
        state = json.loads(current_path.read_text())
        if state["event_index"] == event_index:
            state["phase"] = "complete"
            _atomic(current_path, state)

    def resume(self, source_fingerprint, plan_hash):
        state = json.loads((self.root / "CURRENT.json").read_text())
        if (
            state["fingerprint"] != source_fingerprint
            or state["plan_hash"] != plan_hash
        ):
            raise ValueError(
                "resume refused: config/model/source/manifest mismatch"
            )
        graphs = {}
        for method, item in state["graphs"].items():
            path = self.root / item["path"]
            if file_sha256(path) != item["sha256"]:
                raise ValueError("checkpoint hash mismatch")
            graphs[method] = pickle.loads(path.read_bytes())
        if set(graphs) != set(self.methods):
            raise ValueError("incomplete checkpoint")
        return graphs, state["event_index"]


def freeze_graph(graph, path, cutoff):
    path = Path(path)
    for node in graph.nodes.values():
        if node.type in ("episodic", "semantic"):
            if graph.segment_times[node.metadata["timestamp"]][1] > cutoff:
                raise ValueError("future memory in snapshot")
    payload = graph_bytes(graph)
    expected = hashlib.sha256(payload).hexdigest()
    if path.exists() and path.read_bytes() != payload:
        raise ValueError("snapshot changed on resume")
    if not path.exists():
        _atomic(path, payload, binary=True)
    return expected
