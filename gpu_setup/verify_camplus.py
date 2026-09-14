#!/usr/bin/env python3
"""Run one CAM++ speaker embedding with the pinned 3D-Speaker source tree."""
from __future__ import annotations
import argparse, hashlib, json, sys
from pathlib import Path
import numpy as np
import torch
import torchaudio

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(8 << 20), b""):
            h.update(block)
    return h.hexdigest()

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("wav", type=Path)
    ap.add_argument("--checkpoint", type=Path, required=True)
    ap.add_argument("--speakerlab-root", type=Path, required=True)
    ap.add_argument("--output", type=Path, default=Path("camplus_embedding.npy"))
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    args = ap.parse_args()
    sys.path.insert(0, str(args.speakerlab_root))
    from speakerlab.models.campplus.DTDNN import CAMPPlus
    from speakerlab.process.processor import FBank
    wav, sample_rate = torchaudio.load(str(args.wav))
    if sample_rate != 16000:
        wav = torchaudio.functional.resample(wav, sample_rate, 16000)
    if wav.shape[0] > 1:
        wav = wav[:1]
    features = FBank(80, sample_rate=16000, mean_nor=True)(wav).unsqueeze(0)
    model = CAMPPlus(feat_dim=80, embedding_size=192)
    state = torch.load(args.checkpoint, map_location="cpu", weights_only=True)
    model.load_state_dict(state)
    model.eval().to(args.device)
    with torch.inference_mode():
        embedding = model(features.to(args.device)).squeeze(0).cpu().numpy().astype(np.float32)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    np.save(args.output, embedding)
    print(json.dumps({
        "model": "iic/speech_campplus_sv_zh_en_16k-common_advanced",
        "revision": "v1.0.0",
        "checkpoint": str(args.checkpoint.resolve()),
        "checkpoint_bytes": args.checkpoint.stat().st_size,
        "checkpoint_sha256": sha256(args.checkpoint),
        "source": "modelscope/3D-Speaker",
        "input": str(args.wav.resolve()),
        "output": str(args.output.resolve()),
        "embedding_shape": list(embedding.shape),
        "embedding_dtype": str(embedding.dtype),
        "device": args.device,
        "l2_norm": float(np.linalg.norm(embedding)),
    }, indent=2))

if __name__ == "__main__":
    main()
