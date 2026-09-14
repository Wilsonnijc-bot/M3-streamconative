#!/usr/bin/env python3
"""Run Buffalo-L face detection and recognition on one image."""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
import cv2
import numpy as np
from insightface.app import FaceAnalysis

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(8 << 20), b""):
            h.update(block)
    return h.hexdigest()

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("image", type=Path)
    ap.add_argument("--model-root", type=Path, required=True, help="Directory containing models/buffalo_l/")
    ap.add_argument("--output", type=Path, default=Path("insightface_embeddings.json"))
    ap.add_argument("--det-size", type=int, default=640)
    args = ap.parse_args()
    image = cv2.imread(str(args.image))
    if image is None:
        raise SystemExit(f"Could not read image: {args.image}")
    app = FaceAnalysis(name="buffalo_l", root=str(args.model_root), allowed_modules=["detection", "recognition"], providers=["CUDAExecutionProvider", "CPUExecutionProvider"])
    app.prepare(ctx_id=0, det_size=(args.det_size, args.det_size))
    records = []
    for index, face in enumerate(app.get(image)):
        embedding = np.asarray(face.embedding, dtype=np.float32)
        records.append({"index": index, "bbox": [float(x) for x in face.bbox], "embedding_shape": list(embedding.shape), "embedding_dtype": str(embedding.dtype), "l2_norm": float(np.linalg.norm(embedding)), "embedding": embedding.tolist()})
    model_dir = args.model_root / "models" / "buffalo_l"
    result = {"model_pack": "buffalo_l", "release": "v0.7", "source": "official InsightFace model zoo", "model_root": str(args.model_root.resolve()), "assets": [{"path": str(p.resolve()), "bytes": p.stat().st_size, "sha256": sha256(p)} for p in sorted(model_dir.glob("*.onnx"))], "input": str(args.image.resolve()), "faces": records}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "faces"}, indent=2))
    print(f"faces_detected={len(records)}")

if __name__ == "__main__":
    main()
