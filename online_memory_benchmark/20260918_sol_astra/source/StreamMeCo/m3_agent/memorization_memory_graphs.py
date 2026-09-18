# Copyright (2025) Bytedance Ltd. and/or its affiliates

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#     http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import os
import json
import logging
import argparse
import glob
import pickle
import time

from mmagent.videograph import VideoGraph
from mmagent.utils.video_processing import process_video_clip
from mmagent.face_processing import process_faces
from mmagent.voice_processing import process_voices
if os.environ.get("EGOLIFE_GEMINI_ONLY") == "1":
    from mmagent.memory_processing_gemini import process_memories, generate_memories
else:
    from mmagent.memory_processing_qwen import process_memories, generate_memories
from mmagent.clip_audit import graph_delta, graph_identity, graph_view, write_json

logger = logging.getLogger(__name__)
processing_config = json.load(open("configs/processing_config.json"))
memory_config = json.load(open("configs/memory_config.json"))

preprocessing = []

def process_segment(video_graph, base64_video, base64_frames, base64_audio,
                    clip_id, sample, clip_path, metrics=None, total_started=None):
    runtime = getattr(video_graph, '_consolidation_runtime', None)
    from contextlib import nullcontext
    # Exact media end time is supplied by the stream scheduler, never wall time.
    context = runtime.segment(clip_id, sample['segment_end_s']) if runtime else nullcontext()
    with context:
        return _process_segment(video_graph, base64_video, base64_frames, base64_audio,
                                clip_id, sample, clip_path, metrics, total_started)


def _process_segment(
    video_graph,
    base64_video,
    base64_frames,
    base64_audio,
    clip_id,
    sample,
    clip_path,
    metrics=None,
    total_started=None,
):
    """Process one clip through a fully updated VideoGraph and write its audit."""
    metrics = metrics if metrics is not None else {}
    total_started = total_started or time.perf_counter()
    save_path = sample["intermediate_outputs"]
    audit_dir = sample.get("clip_audit_dir", os.path.join(save_path, "audits"))
    os.makedirs(audit_dir, exist_ok=True)
    before_nodes, before_edges = graph_identity(video_graph)

    voice_metrics = {}
    id2voices = process_voices(
        video_graph,
        base64_audio,
        base64_video,
        save_path=os.path.join(save_path, f"clip_{clip_id}_voices.json"),
        preprocessing=[],
        metrics=voice_metrics,
        prepared_asr=sample.get("prepared_asr"),
    )

    face_metrics = {}
    id2faces = process_faces(
        video_graph,
        base64_frames,
        save_path=os.path.join(save_path, f"clip_{clip_id}_faces.json"),
        preprocessing=[],
        metrics=face_metrics,
    )

    vlm_metrics = {}
    episodic_memories, semantic_memories = generate_memories(
        base64_frames,
        id2faces,
        id2voices,
        clip_path,
        metrics=vlm_metrics,
    )
    generated_memory = {
        "video_description": list(episodic_memories),
        "high_level_conclusions": list(semantic_memories),
    }
    override_path = os.path.join(audit_dir, f"clip_{clip_id}_memory_override.json")
    if not os.path.exists(override_path):
        write_json(override_path, {
            "video_description": None,
            "high_level_conclusions": None,
        })
    with open(override_path) as handle:
        override = json.load(handle)
    effective_memory = {
        key: list(value) for key, value in generated_memory.items()
    }
    override_applied = {}
    for key in ("video_description", "high_level_conclusions"):
        replacement = override.get(key)
        if replacement is not None:
            if not isinstance(replacement, list) or not all(
                isinstance(value, str) for value in replacement
            ):
                raise ValueError(f"{override_path}: {key} must be null or a list of strings")
            effective_memory[key] = replacement
            override_applied[key] = True
        else:
            override_applied[key] = False

    from mmagent.utils.chat_api import get_embeddings_batch
    batch_metrics = {"segment_id":clip_id}
    all_texts = effective_memory['video_description'] + effective_memory['high_level_conclusions']
    from mmagent.character_identity import prepare_texts
    retrieval_texts = prepare_texts(video_graph, all_texts)
    all_vectors, _ = get_embeddings_batch('text-embedding-3-large', retrieval_texts, metrics=batch_metrics)
    split = len(effective_memory['video_description'])
    episodic_metrics = {}
    semantic_metrics = {}
    process_memories(
        video_graph,
        effective_memory["video_description"],
        clip_id,
        type="episodic",
        metrics=episodic_metrics,
        precomputed_embeddings=all_vectors[:split],
        precomputed_contents=retrieval_texts[:split],
    )
    process_memories(
        video_graph,
        effective_memory["high_level_conclusions"],
        clip_id,
        type="semantic",
        metrics=semantic_metrics,
        precomputed_embeddings=all_vectors[split:],
        precomputed_contents=retrieval_texts[split:],
    )

    video_graph.refresh_equivalences()
    total_ms = (time.perf_counter() - total_started) * 1000
    graph = graph_view(video_graph)
    delta = graph_delta(video_graph, before_nodes, before_edges)
    graph_json_path = os.path.join(audit_dir, f"clip_{clip_id}_graph.json")
    graph_pickle_path = os.path.join(audit_dir, f"clip_{clip_id}_graph.pkl")
    if sample.get("persist_clip_graphs", True):
        write_json(graph_json_path, graph)
    temp_pickle = graph_pickle_path + ".tmp"
    if sample.get("persist_clip_graphs", True):
        with open(temp_pickle, "wb") as handle:
            pickle.dump(video_graph, handle)
        os.replace(temp_pickle, graph_pickle_path)

    text_embedding_ms = batch_metrics['latency_ms']
    for subtype in (episodic_metrics, semantic_metrics):
        subtype['text_embedding_ms'] = None
        subtype['embedding_timing_scope'] = 'shared_clip_batch'
    graph_update_ms = sum(
        value or 0.0
        for value in (
            voice_metrics.get("graph_update_ms"),
            face_metrics.get("graph_update_ms"),
            episodic_metrics.get("graph_update_ms"),
            semantic_metrics.get("graph_update_ms"),
        )
    )
    audit = {
        "clip_id": clip_id,
        "voice_observations": [{"voice_node_id": node, **{k: v for k, v in a.items() if k not in ("embedding", "audio_segment")}} for node, audios in id2voices.items() for a in audios],
        "clip_path": str(clip_path),
        "shared_asr_provenance": sample.get("asr_context"),
        "asr_selected_provider": voice_metrics.get("asr_selected_provider"),
        "end_to_end_memory_generation_ms": total_ms,
        "latency_ms": {
            "clip_decode": metrics.get("clip_decode_ms"),
            "deepgram_asr": voice_metrics.get("asr_provider_ms", {}).get("deepgram-asr"),
            "mai_transcribe_asr": voice_metrics.get("asr_provider_ms", {}).get("openrouter-mai-transcribe-2"),
            "asr_total": voice_metrics.get("asr_total_ms"),
            "audio_segmentation": voice_metrics.get("audio_segmentation_ms"),
            "speech_embedding_campplus": voice_metrics.get("speech_embedding_ms"),
            "speech_embedding_ecapa": voice_metrics.get("tst_embedding_ms"),
            "speaker_mapping_including_embedding": voice_metrics.get("speaker_mapping_ms"),
            "facial_detection_recognition_buffalo_l": face_metrics.get("face_detection_recognition_ms"),
            "face_clustering": face_metrics.get("face_clustering_ms"),
            "vlm_memory_generation": vlm_metrics.get("vlm_ms"),
            "text_embedding": text_embedding_ms,
            "graph_update_total": graph_update_ms,
        },
        "stage_details": {
            "text_embedding_batch": batch_metrics,
            "voice": voice_metrics,
            "face": face_metrics,
            "vlm": vlm_metrics,
            "episodic_memory": episodic_metrics,
            "semantic_memory": semantic_metrics,
        },
        "counts": {
            "input_frames": len(base64_frames),
            "asr_segments": voice_metrics.get("asr_segment_count", 0),
            "speech_embeddings": voice_metrics.get("speech_embedding_count", 0),
            "voice_identities": len(id2voices),
            "detected_faces": face_metrics.get("detected_face_count", 0),
            "qualified_faces": face_metrics.get("qualified_face_count", 0),
            "face_identities": len(id2faces),
            "episodic_memories": len(effective_memory["video_description"]),
            "semantic_memories": len(effective_memory["high_level_conclusions"]),
            "nodes_after_clip": graph["counts"]["nodes"],
            "edges_after_clip": graph["counts"]["edges"],
            "nodes_added_by_clip": delta["nodes_added"],
            "edges_added_by_clip": delta["edges_added"],
        },
        "generated_memory": generated_memory,
        "effective_memory": effective_memory,
        "override": {
            "path": override_path,
            "applied": override_applied,
        },
        "graph_delta": delta,
        "artifacts": {
            "readable_graph_json": graph_json_path,
            "exact_graph_pickle": graph_pickle_path,
        },
    }
    audit_path = os.path.join(audit_dir, f"clip_{clip_id}_audit.json")
    write_json(audit_path, audit)
    return audit

def streaming_process_video(video_graph, sample):
    """Process video segments at specified intervals with given fps.

    Args:
        video_graph (VideoGraph): Graph object to store video information
        video_path (str): Path to the video file or directory containing clips
        interval_seconds (float): Time interval between segments in seconds
        fps (float): Frames per second to extract from each segment

    Returns:
        None: Updates video_graph in place with processed segments
    """
    clips = glob.glob(sample["clip_path"] + "/*")
    for clip_path in clips:
        clip_id = int(clip_path.split("/")[-1].split(".")[0])
        total_started = time.perf_counter()
        decode_started = time.perf_counter()
        base64_video, base64_frames, base64_audio = process_video_clip(clip_path)
        metrics = {
            "clip_decode_ms": (time.perf_counter() - decode_started) * 1000
        }

        # Process frames for this interval
        if base64_frames:
            process_segment(
                video_graph,
                base64_video,
                base64_frames,
                base64_audio,
                clip_id,
                sample,
                clip_path,
                metrics=metrics,
                total_started=total_started,
            )
    
    video_graph.refresh_equivalences()
    with open(sample["mem_path"], "wb") as f:
        pickle.dump(video_graph, f)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data_file", type=str, default="streammeco/memory_videmme.jsonl")
    args = parser.parse_args()
    video_inputs = []
    
    with open(args.data_file, "r") as f:
        for line in f:
            sample = json.loads(line)
            if not os.path.exists(sample["mem_path"]):
                video_graph = VideoGraph(**memory_config)
                streaming_process_video(video_graph, sample)
