"""Lazy SpeechBrain adapter; model acquisition is the only network-capable stage."""

import hashlib
import importlib.metadata
from pathlib import Path

import numpy as np

from .audio import file_hash


class SpeechBrainEncoder:
    def __init__(self, config, model_dir):
        import torch
        from huggingface_hub import snapshot_download

        self.torch = torch
        self.device = config["device"]
        if self.device.startswith("cuda") and not torch.cuda.is_available():
            raise ValueError("CUDA requested but unavailable")
        revision = config["revision"]
        local = snapshot_download(
            repo_id="speechbrain/spkrec-ecapa-voxceleb",
            revision=revision,
            local_files_only=config.get("offline", False),
        )
        resolved = Path(local).resolve()
        if resolved.name != revision:
            raise ValueError(
                "model revision did not resolve to requested immutable commit"
            )
        self.asset_hashes = {
            name: file_hash(resolved / name)
            for name in (
                "hyperparams.yaml",
                "embedding_model.ckpt",
                "mean_var_norm_emb.ckpt",
                "classifier.ckpt",
                "label_encoder.txt",
            )
        }
        self.checkpoint_hash = self.asset_hashes["embedding_model.ckpt"]
        self.preprocessing_hash = self.asset_hashes["hyperparams.yaml"]
        self.revision = revision
        self.versions = {
            p: importlib.metadata.version(p)
            for p in (
                "speechbrain",
                "torch",
                "huggingface-hub",
                "numpy",
                "soundfile",
                "scipy",
            )
        }
        try:
            from speechbrain.inference.classifiers import EncoderClassifier
        except ImportError:
            from speechbrain.pretrained import EncoderClassifier
        self.model = EncoderClassifier.from_hparams(
            source=str(resolved),
            savedir=str(model_dir),
            run_opts={"device": self.device},
            overrides={"pretrained_path": str(resolved)},
        )
        self.model.eval()
        self.fingerprint = hashlib.sha256(
            (
                str(sorted(self.asset_hashes.items()))
                + str(sorted(self.versions.items()))
                + "first-channel:resample_poly:16000:raw-encoder-output:v1"
            ).encode()
        ).hexdigest()

    def encode(self, waveform):
        tensor = self.torch.from_numpy(np.asarray(waveform, dtype=np.float32)).to(
            self.device
        )[None, :]
        with self.torch.inference_mode():
            result = (
                self.model.encode_batch(tensor, normalize=False)
                .detach()
                .cpu()
                .numpy()
                .reshape(-1)
            )
        if self.device.startswith("cuda"):
            self.torch.cuda.synchronize(self.device)
        return result
