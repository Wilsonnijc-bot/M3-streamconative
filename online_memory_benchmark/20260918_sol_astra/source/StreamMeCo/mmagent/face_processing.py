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
from concurrent.futures import ThreadPoolExecutor
from tqdm import tqdm
import json
import os
import logging
import time
from insightface.app import FaceAnalysis
from mmagent.src.face_extraction import extract_faces
from mmagent.src.face_clustering import cluster_faces
from mmagent.utils.video_processing import process_video_clip

processing_config = json.load(open("configs/processing_config.json"))
face_app = None
cluster_size = processing_config["cluster_size"]
logger = logging.getLogger(__name__)

class Face:
    def __init__(self, frame_id, bounding_box, face_emb, cluster_id, extra_data):
        self.frame_id = frame_id
        self.bounding_box = bounding_box
        self.face_emb = face_emb
        self.cluster_id = cluster_id
        self.extra_data = extra_data

def get_face(frames):
    global face_app
    if face_app is None:
        model_name = processing_config.get("face_model", "buffalo_l")
        model_root = os.environ.get(
            "INSIGHTFACE_MODEL_ROOT",
            processing_config.get("face_model_root", "models/insightface"),
        )
        face_app = FaceAnalysis(
            name=model_name,
            root=model_root,
            allowed_modules=["detection", "recognition"],
            providers=["CUDAExecutionProvider", "CPUExecutionProvider"],
        )
        face_app.prepare(ctx_id=0)
    extracted_faces = extract_faces(face_app, frames, num_workers=1)
    faces = [Face(frame_id=f['frame_id'], bounding_box=f['bounding_box'], face_emb=f['face_emb'], cluster_id=f['cluster_id'], extra_data=f['extra_data']) for f in extracted_faces]
    return faces

def cluster_face(faces):
    faces_json = [{'frame_id': f.frame_id, 'bounding_box': f.bounding_box, 'face_emb': f.face_emb, 'cluster_id': f.cluster_id, 'extra_data': f.extra_data} for f in faces]
    clustered_faces = cluster_faces(faces_json, 20, 0.5)
    faces = [Face(frame_id=f['frame_id'], bounding_box=f['bounding_box'], face_emb=f['face_emb'], cluster_id=f['cluster_id'], extra_data=f['extra_data']) for f in clustered_faces]
    return faces

def process_faces(
    video_graph, base64_frames, save_path, preprocessing=[], metrics=None
):
    """Run Buffalo-L detection/recognition, clustering, and graph association."""
    metrics = metrics if metrics is not None else {}
    total_started = time.perf_counter()
    metrics.update({
        "cache_hit": False,
        "face_detection_recognition_ms": None,
        "face_clustering_ms": None,
        "graph_update_ms": None,
        "frame_count": len(base64_frames),
        "detected_face_count": 0,
        "qualified_face_count": 0,
        "raw_cluster_count": 0,
        "face_identity_count": 0,
    })

    def finish(value):
        metrics["total_ms"] = (time.perf_counter() - total_started) * 1000
        return value

    batch_size = max(len(base64_frames) // cluster_size, 4)

    def process_batch(params):
        frames, offset = params
        faces = get_face(frames)
        for face in faces:
            face.frame_id += offset
        return faces

    def get_embeddings(frames):
        num_batches = (len(frames) + batch_size - 1) // batch_size
        batched_frames = [
            (frames[index * batch_size:(index + 1) * batch_size], index * batch_size)
            for index in range(num_batches)
        ]
        faces = []
        inference_started = time.perf_counter()
        with ThreadPoolExecutor(
            max_workers=min(num_batches, processing_config.get("face_gpu_workers", 1))
        ) as executor:
            for batch_faces in tqdm(executor.map(process_batch, batched_frames), total=num_batches):
                faces.extend(batch_faces)
        metrics["face_detection_recognition_ms"] = (
            time.perf_counter() - inference_started
        ) * 1000
        metrics["detected_face_count"] = len(faces)
        cluster_started = time.perf_counter()
        faces = cluster_face(faces)
        metrics["face_clustering_ms"] = (
            time.perf_counter() - cluster_started
        ) * 1000
        return faces

    def establish_mapping(faces, key="cluster_id", filter=None):
        mapping = {}
        for face in faces:
            if key not in face:
                raise ValueError(f"key {key} not found in faces")
            if filter and not filter(face):
                continue
            mapping.setdefault(face[key], []).append(face)
        max_faces = processing_config["max_faces_per_character"]
        for identity in mapping:
            mapping[identity] = sorted(
                mapping[identity],
                key=lambda value: (
                    float(value["extra_data"]["face_detection_score"]),
                    float(value["extra_data"]["face_quality_score"]),
                ),
                reverse=True,
            )[:max_faces]
        return mapping

    def filter_score_based(face):
        return (
            float(face["extra_data"]["face_detection_score"])
            > processing_config["face_detection_score_threshold"]
            and float(face["extra_data"]["face_quality_score"])
            > processing_config["face_quality_score_threshold"]
        )

    def update_videograph(tempid2faces):
        id2faces = {}
        for tempid, faces in tempid2faces.items():
            if tempid == -1 or not faces:
                continue
            face_info = {
                "embeddings": [face["face_emb"] for face in faces],
                "contents": [face["extra_data"]["face_base64"] for face in faces],
            }
            matched_nodes = video_graph.search_img_nodes(face_info)
            if matched_nodes:
                matched_node = matched_nodes[0][0]
                video_graph.update_node(matched_node, face_info)
            else:
                matched_node = video_graph.add_img_node(face_info)
            for face in faces:
                face["matched_node"] = matched_node
            id2faces.setdefault(matched_node, []).extend(faces)
        max_faces = processing_config["max_faces_per_character"]
        for identity, faces in id2faces.items():
            id2faces[identity] = sorted(
                faces,
                key=lambda value: (
                    float(value["extra_data"]["face_detection_score"]),
                    float(value["extra_data"]["face_quality_score"]),
                ),
                reverse=True,
            )[:max_faces]
        return id2faces

    try:
        cache_started = time.perf_counter()
        with open(save_path, "r") as handle:
            faces_json = json.load(handle)
        metrics["cache_hit"] = True
        metrics["cache_load_ms"] = (time.perf_counter() - cache_started) * 1000
        metrics["detected_face_count"] = len(faces_json)
    except Exception:
        metrics["cache_hit"] = False
        faces = get_embeddings(base64_frames)
        faces_json = [
            {
                "frame_id": face.frame_id,
                "bounding_box": face.bounding_box,
                "face_emb": face.face_emb,
                "cluster_id": int(face.cluster_id),
                "extra_data": face.extra_data,
            }
            for face in faces
        ]
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        with open(save_path, "w") as handle:
            json.dump(faces_json, handle)

    metrics["raw_cluster_count"] = len({
        face.get("cluster_id") for face in faces_json if face.get("cluster_id") != -1
    })
    if "face" in preprocessing or not faces_json:
        return finish({})
    tempid2faces = establish_mapping(
        faces_json, key="cluster_id", filter=filter_score_based
    )
    metrics["qualified_face_count"] = sum(len(values) for values in tempid2faces.values())
    if not tempid2faces:
        return finish({})
    graph_started = time.perf_counter()
    id2faces = update_videograph(tempid2faces)
    metrics["graph_update_ms"] = (time.perf_counter() - graph_started) * 1000
    metrics["face_identity_count"] = len(id2faces)
    return finish(id2faces)

def main():
    _, frames, _ = process_video_clip(
        "/mnt/hdfs/foundation/longlin.kylin/mmagent/data/video_clips/CZ_2/-OCrS_r5GHc/11.mp4"
    )
    process_faces(None, frames, "data/temp/face_detection_results.json", preprocessing=["face"])

if __name__ == "__main__":
    main()