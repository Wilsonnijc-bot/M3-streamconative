from types import SimpleNamespace
import pickle

import numpy as np

from mmagent.speaker_mapping import assign_voice, score_candidates


class Graph:
    def __init__(self):
        self.nodes = {}
        self.next_node_id = 0
        self.audio_matching_threshold = 0.6
        self.max_audio_embeddings = 20

    def search_voice_nodes(self, audio_info):
        candidates = score_candidates(self, audio_info["embeddings"])
        matches = [
            (int(candidate["candidate_id"].split("_")[-1]), candidate["score"])
            for candidate in candidates
            if candidate["eligible"]
        ]
        return sorted(matches, key=lambda item: item[1], reverse=True)

    def add_voice_node(self, audio_info):
        node_id = self.next_node_id
        self.next_node_id += 1
        self.nodes[node_id] = SimpleNamespace(
            id=node_id,
            type="voice",
            embeddings=list(audio_info["embeddings"]),
            metadata={"contents": list(audio_info["contents"])},
        )
        return node_id

    def update_node(self, node_id, audio_info):
        node = self.nodes[node_id]
        node.embeddings.extend(audio_info["embeddings"])
        node.metadata["contents"].extend(audio_info["contents"])


def test_native_assignment_records_candidates_before_mutation():
    graph = Graph()
    node_id, first = assign_voice(graph, [[1.0, 0.0]], "first", method="CAM++")
    assert node_id == 0
    assert first["created_new_identity"] is True
    assert first["candidates"] == []

    node_id, second = assign_voice(
        graph,
        [np.array([0.9, 0.1])],
        "second",
        method="TST",
        method_id="ecapa-test",
    )
    assert node_id == 0
    assert second["created_new_identity"] is False
    assert second["method"] == "TST"
    assert second["method_id"] == "ecapa-test"
    assert second["predicted_identity"] == "voice_0"
    assert second["candidates"][0]["eligible"] is True
    assert second["retained_embeddings"] == 2


def test_native_assignment_creates_identity_below_threshold():
    graph = Graph()
    assign_voice(graph, [[1.0, 0.0]], "first", method="CAM++")
    node_id, mapping = assign_voice(
        graph, [[0.0, 1.0]], "different", method="CAM++"
    )
    assert node_id == 1
    assert mapping["created_new_identity"] is True
    assert mapping["candidates"][0]["eligible"] is False
    assert mapping["candidate_scores"] == {"voice_0": 0.0}


def test_graph_serialization_drops_runtime_mapper():
    from mmagent.videograph import VideoGraph

    graph = VideoGraph()
    graph.speaker_mapper = object()
    restored = pickle.loads(pickle.dumps(graph))
    assert not hasattr(restored, "speaker_mapper")
