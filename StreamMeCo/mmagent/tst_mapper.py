"""Online ECAPA/TST speaker encoder using M3's native identity policy."""

import base64
import hashlib
import io
import json
from pathlib import Path
import time
import wave

from .speaker_mapping import assign_voice


class TSTVoiceMapper:
    def __init__(self, root, config_path, encoder=None):
        from tst.audio import AudioExtractor
        from tst.encoder import SpeechBrainEncoder

        self.root = Path(root)
        self.config = json.loads(Path(config_path).read_text())
        config = self.config
        if (
            config["enrollment_policy"] != "online_native_m3"
            or config["pre_enrollment"] is not False
        ):
            raise ValueError("TST must use online native enrollment")
        self.encoder = encoder or SpeechBrainEncoder(
            {
                "revision": config["encoder"]["revision"],
                "device": "cuda",
                "offline": True,
            },
            self.root / "tst_assets/ecapa_model",
        )
        if self.encoder.fingerprint != config["encoder_fingerprint"]:
            raise ValueError("ECAPA fingerprint mismatch")
        self.extractor = AudioExtractor(
            self.encoder,
            self.encoder.fingerprint,
            self.root / "cache/ecapa_embeddings",
        )

    def map(self, graph, segment, transcript):
        began = time.perf_counter()
        config = self.config
        if (
            graph.audio_matching_threshold != config["threshold"]
            or graph.max_audio_embeddings != config["max_audio_embeddings"]
        ):
            raise ValueError("native speaker policy mismatch")
        previous = getattr(graph, "speaker_encoder_fingerprint", None)
        if previous not in (None, config["encoder_fingerprint"]):
            raise ValueError("mixed speaker encoder spaces")
        voices = [node for node in graph.nodes.values() if node.type == "voice"]
        if any(
            node.metadata.get("embedding_space") != "speechbrain_ecapa_192"
            for node in voices
        ):
            raise ValueError("non-ECAPA vectors in TST graph")
        graph.speaker_encoder_fingerprint = config["encoder_fingerprint"]

        data = base64.b64decode(segment)
        audio_sha256 = hashlib.sha256(data).hexdigest()
        path = self.root / "cache/tst_query_audio" / f"{audio_sha256}.wav"
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_bytes(data)
        with wave.open(io.BytesIO(data)) as wav:
            duration = wav.getnframes() / wav.getframerate()
        vectors, cache_hit, embedding_ms = self.extractor.extract(
            {"audio_path": str(path), "start_s": 0.0, "end_s": duration}
        )
        node_id, mapping = assign_voice(
            graph,
            vectors.tolist(),
            transcript,
            method="TST",
            method_id=config["method_id"],
            details={
                "cache_hit": cache_hit,
                "embedding_ms": embedding_ms,
                "audio_sha256": audio_sha256,
                "query_window_count": len(vectors),
            },
        )
        graph.nodes[node_id].metadata.update(
            speaker_mapping="TST",
            embedding_space="speechbrain_ecapa_192",
            method_id=config["method_id"],
        )
        mapping["mapping_total_ms"] = (time.perf_counter() - began) * 1000
        return node_id, mapping
