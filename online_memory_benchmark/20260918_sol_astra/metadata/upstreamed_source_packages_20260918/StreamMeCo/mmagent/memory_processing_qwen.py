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
import ast
import json
import logging
import os
import re
import time
from io import BytesIO

import numpy as np
import matplotlib.pyplot as plt
from PIL import Image, ImageDraw

from .utils.chat_api import parallel_get_embedding, get_embeddings_batch
from .utils.general import validate_and_fix_json
from .prompts import prompt_generate_memory_with_ids_sft
from .memory_processing import parse_video_caption

processing_config = json.load(open("configs/processing_config.json"))
logging_level = processing_config["logging"]

MAX_RETRIES = processing_config["max_retries"]
# Configure logging
logger = logging.getLogger(__name__)


def generate_messages(*args, **kwargs):
    from .utils.chat_qwen import generate_messages as generate
    return generate(*args, **kwargs)


def get_response(*args, **kwargs):
    from .utils.chat_qwen import get_response as respond
    return respond(*args, **kwargs)


def _parse_memory_object(raw_response):
    parsed = validate_and_fix_json(raw_response)
    if isinstance(parsed, dict):
        return parsed
    text = (raw_response or "").strip()
    decoder = json.JSONDecoder()
    for start, char in enumerate(text):
        if char != "{":
            continue
        try:
            candidate, _ = decoder.raw_decode(text[start:])
        except json.JSONDecodeError:
            continue
        if isinstance(candidate, dict):
            return candidate
    first, last = text.find("{"), text.rfind("}")
    if first >= 0 and last > first:
        try:
            candidate = ast.literal_eval(text[first:last + 1])
        except (SyntaxError, ValueError):
            return None
        if isinstance(candidate, dict):
            return candidate
    return None


def _normalize_memory(raw_response):
    parsed = _parse_memory_object(raw_response)
    if not isinstance(parsed, dict):
        raise ValueError("VLM response is not a valid memory object")
    episodic = parsed.get(
        "video_descriptions",
        parsed.get("video_description", parsed.get("episodic_memory")),
    )
    semantic = parsed.get(
        "high_level_conclusions", parsed.get("semantic_memory")
    )
    for label, values in (("episodic", episodic), ("semantic", semantic)):
        if not isinstance(values, list) or not values:
            raise ValueError(f"VLM response has no nonempty {label} memory list")
        if any(not isinstance(value, str) or not value.strip() for value in values):
            raise ValueError(f"VLM {label} memory must contain nonempty strings")
    return {
        "video_description": [value.strip() for value in episodic],
        "high_level_conclusions": [value.strip() for value in semantic],
    }


def _clean_prose_item(line):
    line = re.sub(r"^\s*(?:[-*]|\d+[.)])\s*", "", line).strip()
    line = line.strip("` \t\"'")
    return line.rstrip(",").strip()


def _recover_memory_from_prose(raw_response):
    """Recover Qwen's requested sections when it omits the final JSON wrapper."""
    sections = {"video_description": [], "high_level_conclusions": []}
    active = None
    for raw_line in (raw_response or "").splitlines():
        line = raw_line.strip()
        normalized = re.sub(r"[^a-z ]+", " ", line.lower())
        normalized = " ".join(normalized.split())
        if any(
            marker in normalized
            for marker in ("high level conclusion", "drafting conclusions", "inferences")
        ):
            active = "high_level_conclusions"
            continue
        if any(
            marker in normalized
            for marker in ("video description", "drafting the content", "observable events")
        ):
            active = "video_description"
            continue
        if not active or not re.match(r"^\s*(?:[-*]|\d+[.)])\s+", raw_line):
            continue
        item = _clean_prose_item(raw_line)
        if not item or len(item) < 8:
            continue
        if item.lower().startswith(("video description", "high level conclusion")):
            continue
        if item not in sections[active]:
            sections[active].append(item)

    if not all(sections.values()):
        raise ValueError("VLM prose did not contain both required memory sections")
    return {
        "video_description": sections["video_description"][:16],
        "high_level_conclusions": sections["high_level_conclusions"][:12],
    }


def _repair_memory_response(raw_response):
    repair_prompt = f"""/no_think
Convert the candidate response below into the exact JSON schema requested by the
original task. Preserve only claims present in the candidate. Return one JSON
object immediately, with no analysis, Markdown, or code fence:
{{"video_description": ["..."], "high_level_conclusions": ["..."]}}

Candidate response:
{(raw_response or '')[-16000:]}
"""
    repair_messages = generate_messages([{"type": "text", "content": repair_prompt}])
    response, _tokens, generation = get_response(
        repair_messages,
        enable_thinking=False,
        max_new_tokens=int(os.environ.get("QWEN_MEMORY_REPAIR_MAX_NEW_TOKENS", "1024")),
        return_details=True,
    )
    return _normalize_memory(response), response, generation


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
    max_attempts = int(os.environ.get("QWEN_MEMORY_MAX_ATTEMPTS", "1"))
    max_new_tokens = int(os.environ.get("QWEN_MEMORY_MAX_NEW_TOKENS", "3072"))
    enable_thinking = os.environ.get(
        "QWEN_MEMORY_ENABLE_THINKING", "false"
    ).strip().lower() in {"1", "true", "yes", "on"}
    validation_errors = []
    invalid_response = ""
    for attempt in range(1, max_attempts + 1):
        attempt_started = time.perf_counter()
        raw_response, _tokens, generation = get_response(
            messages,
            enable_thinking=enable_thinking,
            max_new_tokens=max_new_tokens * (2 ** (attempt - 1)),
            return_details=True,
        )
        attempt_metrics = {
            "attempt": attempt,
            "max_new_tokens": max_new_tokens * (2 ** (attempt - 1)),
            "latency_ms": (time.perf_counter() - attempt_started) * 1000,
            "response_chars": len(raw_response or ""),
            "generation": generation,
            "enable_thinking": enable_thinking,
        }
        if not raw_response:
            attempt_metrics["validation_error"] = "empty response"
            metrics.setdefault("attempts", []).append(attempt_metrics)
            continue
        try:
            memories = _normalize_memory(raw_response)
        except ValueError as error:
            attempt_metrics["validation_error"] = str(error)
            validation_errors.append(str(error))
            invalid_response = raw_response
        else:
            metrics.setdefault("attempts", []).append(attempt_metrics)
            break
        metrics.setdefault("attempts", []).append(attempt_metrics)
    if not isinstance(memories, dict) and invalid_response:
        try:
            memories = _recover_memory_from_prose(invalid_response)
        except ValueError as prose_error:
            validation_errors.append(str(prose_error))
        else:
            metrics["recovery"] = {
                "method": "deterministic_prose_sections",
                "input_chars": len(invalid_response),
            }
    if not isinstance(memories, dict) and invalid_response:
        repair_started = time.perf_counter()
        try:
            memories, repair_response, repair_generation = _repair_memory_response(
                invalid_response
            )
        except ValueError as repair_error:
            validation_errors.append(f"repair: {repair_error}")
        else:
            metrics["recovery"] = {
                "method": "qwen_text_repair",
                "latency_ms": (time.perf_counter() - repair_started) * 1000,
                "input_chars": len(invalid_response),
                "response_chars": len(repair_response),
                "generation": repair_generation,
            }
    metrics["vlm_ms"] = (time.perf_counter() - generation_started) * 1000
    metrics["raw_response"] = raw_response
    metrics["valid_memory_json"] = isinstance(memories, dict)
    if not isinstance(memories, dict):
        preview = (invalid_response or raw_response or "")[-1500:].replace("\x00", "")
        raise ValueError(
            f"Qwen failed memory validation after {max_attempts} attempts: "
            f"{validation_errors}; final_response_tail={preview!r}"
        )
    episodic_memories = memories["video_description"]
    semantic_memories = memories["high_level_conclusions"]
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
    precomputed_embeddings=None, precomputed_embedding_ms=None, precomputed_contents=None,
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
    from .character_identity import prepare_texts, consolidated
    retrieval_texts = prepare_texts(video_graph, memory_contents)
    if precomputed_embeddings is None:
        embedding_started = time.perf_counter()
        embeddings = get_embeddings_batch(
            "text-embedding-3-large", retrieval_texts
        )[0]
        metrics["text_embedding_ms"] = (
            time.perf_counter() - embedding_started
        ) * 1000
        metrics["text_embedding_execution"] = "current_process"
    else:
        if consolidated(video_graph) and precomputed_contents != retrieval_texts:
            raise ValueError('precomputed embedding input does not match canonical retrieval text')
        embeddings = precomputed_embeddings
        if len(embeddings) != len(memory_contents):
            raise ValueError("precomputed embedding count does not match memories")
        metrics["text_embedding_ms"] = float(precomputed_embedding_ms or 0.0)
        metrics["text_embedding_execution"] = "precomputed_handoff"
    metrics["text_embedding_count"] = len(embeddings)
    memories = [
        {"contents": [memory], "embeddings": [embedding], "retrieval_contents": [retrieval]}
        for memory, retrieval, embedding in zip(memory_contents, retrieval_texts, embeddings)
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
