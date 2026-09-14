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
import base64
import json
import logging
import time
from io import BytesIO

import numpy as np
import matplotlib.pyplot as plt
from PIL import Image, ImageDraw

from .utils.chat_api import parallel_get_embedding
from .utils.chat_qwen import generate_messages, get_response
from .utils.general import validate_and_fix_json
from .prompts import prompt_generate_memory_with_ids_sft
from .memory_processing import parse_video_caption

processing_config = json.load(open("configs/processing_config.json"))
logging_level = processing_config["logging"]

MAX_RETRIES = processing_config["max_retries"]
# Configure logging
logger = logging.getLogger(__name__)

def generate_video_context(
    base64_frames, faces_list, voices_list, video_path=None, faces_input="face_only"
):
    face_frames = []
    face_only = []

    # Iterate through faces directly
    for char_id, faces in faces_list.items():
        if len(faces) == 0:
            continue
        face = faces[0]
        frame_id = face["frame_id"]
        frame_base64 = base64_frames[frame_id]

        # Convert base64 to PIL Image
        frame_bytes = base64.b64decode(frame_base64)
        frame_img = Image.open(BytesIO(frame_bytes))
        draw = ImageDraw.Draw(frame_img)

        # Draw current face
        bbox = face["bounding_box"]
        draw.rectangle(
            [(bbox[0], bbox[1]), (bbox[2], bbox[3])], outline=(0, 255, 0), width=4
        )

        # Convert back to base64
        buffered = BytesIO()
        frame_img.save(buffered, format="JPEG")
        frame_base64 = base64.b64encode(buffered.getvalue()).decode()
        face_frames.append((f"<face_{char_id}>:", frame_base64))
        face_only.append((f"<face_{char_id}>:", face["extra_data"]["face_base64"]))
    
    if faces_input == "face_only":
        faces_input = face_only
    elif faces_input == "face_frames":
        faces_input = face_frames
    else:
        raise ValueError(f"Invalid face input: {faces_input}")
    
    num_faces = len(faces_input)
    if num_faces == 0:
        logger.warning("No qualified faces detected")
    
    # Visualize face frames with IDs
    if logging_level == "DETAIL" and num_faces > 0:
        num_rows = (num_faces + 2) // 3  # Round up division to get number of rows needed

        _, axes = plt.subplots(num_rows, 3, figsize=(15, 5 * num_rows))
        axes = axes.ravel()  # Flatten axes array for easier indexing

        for i, face_pic in enumerate(faces_input):
            # Convert base64 to image array
            img_bytes = base64.b64decode(face_pic[1])
            img_array = np.array(Image.open(BytesIO(img_bytes)))

            axes[i].imshow(img_array)
            axes[i].set_title(face_pic[0])
            axes[i].axis("off")

        # Hide empty subplots
        for j in range(i + 1, len(axes)):
            axes[j].axis("off")

        plt.tight_layout()
        plt.show()

    voices_input = {}
    for id, voices in voices_list.items():
        if len(voices) == 0:
            continue
        voices_input[f"<voice_{id}>"] = [{
            "start_time": voice["start_time"],
            "end_time": voice["end_time"],
            "asr": voice["asr"]
        } for voice in voices]
    
    num_voices = len(voices_input)
    if num_voices == 0:
        logger.warning("No qualified voices detected")

    if logging_level == "DETAIL" and num_voices > 0:
        logger.debug(f"Diarized dialogues: {voices_input}")

    video_context = [
        {
            "type": "video_base64/mp4",
            "content": video_path,
        },
        {
            "type": "text",
            "content": "Face features:"
        },
        {
            "type": "images/jpeg",
            "content": faces_input,
        },
        {
            "type": "text",
            "content": "Voice features:"
        },
        {
            "type": "text",
            "content": json.dumps(voices_input),
        }
    ]

    return video_context

def generate_all_memories(video_context, model_type="sft", metrics=None):
    metrics = metrics if metrics is not None else {}
    inputs = [{"type": "text", "content": prompt_generate_memory_with_ids_sft}] + video_context
    messages = generate_messages(inputs)
    memories = None
    raw_response = ""
    generation_started = time.perf_counter()
    for attempt in range(1, MAX_RETRIES + 1):
        attempt_started = time.perf_counter()
        raw_response = get_response(messages, enable_thinking=True)[0]
        metrics.setdefault("attempts", []).append({
            "attempt": attempt,
            "latency_ms": (time.perf_counter() - attempt_started) * 1000,
            "response_chars": len(raw_response or ""),
        })
        if not raw_response:
            continue
        memories = validate_and_fix_json(raw_response)
        if isinstance(memories, dict):
            break
    metrics["vlm_ms"] = (time.perf_counter() - generation_started) * 1000
    metrics["raw_response"] = raw_response
    metrics["valid_memory_json"] = isinstance(memories, dict)
    if not isinstance(memories, dict):
        memories = {"video_descriptions": [], "high_level_conclusions": []}
    episodic_memories = memories.get(
        "video_descriptions", memories.get("video_description", [])
    )
    semantic_memories = memories.get("high_level_conclusions", [])
    metrics["generated_memory"] = {
        "video_description": episodic_memories,
        "high_level_conclusions": semantic_memories,
    }
    metrics["episodic_memory_count"] = len(episodic_memories)
    metrics["semantic_memory_count"] = len(semantic_memories)
    return episodic_memories, semantic_memories


def generate_memories(
    base64_frames, faces_list, voices_list, video_path, model_type="sft", metrics=None
):
    context_started = time.perf_counter()
    video_context = generate_video_context(
        base64_frames, faces_list, voices_list, video_path
    )
    if metrics is not None:
        metrics["context_preparation_ms"] = (
            time.perf_counter() - context_started
        ) * 1000
    return generate_all_memories(video_context, model_type, metrics=metrics)

def process_memories(
    video_graph, memory_contents, clip_id, type="episodic", metrics=None,
    precomputed_embeddings=None, precomputed_embedding_ms=None,
):
    """Embed generated text and apply its node/edge mutations to the graph."""
    metrics = metrics if metrics is not None else {}
    metrics.update({
        "memory_type": type,
        "input_count": len(memory_contents),
        "text_embedding_ms": 0.0,
        "text_embedding_count": 0,
        "graph_update_ms": 0.0,
        "nodes_added": 0,
        "directed_edges_added": 0,
    })
    if not memory_contents:
        return metrics

    nodes_before = set(video_graph.nodes)
    edges_before = set(video_graph.edges)
    if precomputed_embeddings is None:
        embedding_started = time.perf_counter()
        embeddings = parallel_get_embedding(
            "text-embedding-3-large", memory_contents
        )[0]
        metrics["text_embedding_ms"] = (
            time.perf_counter() - embedding_started
        ) * 1000
        metrics["text_embedding_execution"] = "current_process"
    else:
        embeddings = precomputed_embeddings
        if len(embeddings) != len(memory_contents):
            raise ValueError("precomputed embedding count does not match memories")
        metrics["text_embedding_ms"] = float(precomputed_embedding_ms or 0.0)
        metrics["text_embedding_execution"] = "precomputed_handoff"
    metrics["text_embedding_count"] = len(embeddings)
    memories = [
        {"contents": [memory], "embeddings": [embedding]}
        for memory, embedding in zip(memory_contents, embeddings)
    ]

    def insert_memory(memory):
        new_node_id = video_graph.add_text_node(memory, clip_id, type)
        entities = parse_video_caption(video_graph, memory["contents"][0])
        for entity in entities:
            video_graph.add_edge(new_node_id, entity[1])

    graph_started = time.perf_counter()
    if type == "episodic":
        for memory in memories:
            insert_memory(memory)
    elif type == "semantic":
        for memory in memories:
            entities = parse_video_caption(video_graph, memory["contents"][0])
            if not entities:
                insert_memory(memory)
                continue
            positive_threshold = 0.85
            negative_threshold = 0
            entity_node_id = entities[0][1]
            related_nodes = video_graph.get_connected_nodes(
                entity_node_id, type=["semantic"]
            )
            create_new_node = True
            for related_node_id in related_nodes:
                related_node_entities = parse_video_caption(
                    video_graph,
                    video_graph.nodes[related_node_id].metadata["contents"][0],
                )
                embedding = video_graph.nodes[related_node_id].embeddings[0]
                if all(entity in related_node_entities for entity in entities):
                    similarity = np.dot(memory["embeddings"][0], embedding) / (
                        np.linalg.norm(memory["embeddings"][0])
                        * np.linalg.norm(embedding)
                    )
                    if similarity > positive_threshold:
                        video_graph.reinforce_node(related_node_id)
                        create_new_node = False
                    elif similarity < negative_threshold:
                        video_graph.weaken_node(related_node_id)
                        create_new_node = False
            if create_new_node:
                insert_memory(memory)
    else:
        raise ValueError("type must be episodic or semantic")
    metrics["graph_update_ms"] = (time.perf_counter() - graph_started) * 1000
    metrics["nodes_added"] = len(set(video_graph.nodes) - nodes_before)
    metrics["directed_edges_added"] = len(set(video_graph.edges) - edges_before)
    return metrics

