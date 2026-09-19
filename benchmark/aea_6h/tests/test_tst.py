import hashlib
import json
import sys
import types
from pathlib import Path
from typing import ClassVar

import numpy as np
import pytest
import soundfile as sf

from tst.audio import windows
from tst.encoder import SpeechBrainEncoder
from tst.runner import run, validate
from tst.scoring import cohort_stats, compensate, matrix, score


class FakeEncoder:
    revision = "a" * 40
    fingerprint = "fake-ecapa-test-v1"
    checkpoint_hash = "fake-checkpoint"
    preprocessing_hash = "fake-preprocessing"
    versions: ClassVar[dict[str, str]] = {"fake": "1"}

    def encode(self, waveform):
        result = np.zeros(192)
        result[0] = float(np.mean(waveform))
        result[1] = 0.25
        return result


def write_jsonl(path, values):
    path.write_text("".join(json.dumps(v) + "\n" for v in values))
    return str(path)


def config(
    normalization="cosine", compensation="none", gallery="all_enrolled", threshold=None
):
    return {
        "diarization_provider": "deepgram-asr",
        "encoder": {
            "model_id": "speechbrain/spkrec-ecapa-voxceleb",
            "revision": "a" * 40,
        },
        "gallery": {"policy": gallery},
        "scoring": {"normalization": normalization, "threshold": threshold},
        "compensation": {"mode": compensation},
        "runtime": {"device": "cpu"},
        "cohort": {
            "corpus": "synthetic",
            "speaker_count": 20,
            "approximate": True,
            "seed": 7,
        },
    }


def setup(tmp_path):
    audio = tmp_path / "audio.wav"
    sf.write(audio, np.full(16000 * 8, 0.5), 16000)
    ref = {"audio_path": str(audio), "start_s": 0, "end_s": 1}
    enrollment = [
        dict(ref, global_speaker_id=g, source_id=g, verification_provenance="human")
        for g in ("A", "B")
    ]
    segments = [
        dict(
            ref,
            session_id=s,
            clip_id=s,
            segment_id=i,
            local_speaker_id=label,
            transcript="hello",
            diarization_provenance="deepgram-asr",
            timestamp_precision="raw",
        )
        for s, i, label in (
            ("clip1", "1", 0),
            ("clip1", "2", 0),
            ("clip2", "3", 0),
            ("clip1", "4", None),
        )
    ]
    paths = {
        "segments": write_jsonl(tmp_path / "segments.jsonl", segments),
        "enrollment": write_jsonl(tmp_path / "enrollment.jsonl", enrollment),
        "cohort": None,
        "session_candidates": None,
    }
    return paths, segments


@pytest.mark.parametrize(
    "samples,expected",
    [
        (8000, [(0, 8000)]),
        (16000, [(0, 16000)]),
        (63999, [(0, 63999)]),
        (64000, [(0, 64000)]),
        (64001, [(0, 64000), (1, 64001)]),
        (88000, [(0, 64000), (24000, 88000)]),
        (88001, [(0, 64000), (24000, 88000), (24001, 88001)]),
        (100000, [(0, 64000), (24000, 88000), (36000, 100000)]),
    ],
)
def test_windows(samples, expected):
    assert windows(samples) == expected


def test_asnorm_hand_computed_and_floor():
    basis = np.eye(192)
    cohort = matrix(np.vstack([basis[0], basis[1], basis[2:20]]))
    e, q = basis[[0]], basis[[1]]
    em, es, floor = cohort_stats(e, cohort)
    assert floor == 0
    assert em[0] == pytest.approx(1 / 20)
    assert es[0] == pytest.approx(np.std([1] + [0] * 19))
    value, _ = score(e, q, "asnorm", cohort)
    assert value == pytest.approx(-em[0] / es[0])
    repeated = matrix(np.repeat(basis[[2]], 20, axis=0))
    _, sig, floors = cohort_stats(e, repeated)
    assert sig[0] == pytest.approx(1e-6) and floors == 1


def test_pairwise_pooling_not_centroid_cosine():
    basis = np.eye(192)
    e = matrix([basis[0], basis[1]])
    q = matrix([basis[0]])
    value, _ = score(e, q)
    assert value == pytest.approx(0.5)
    assert value != pytest.approx(unit_cos(e.mean(axis=0), q.mean(axis=0)))


def unit_cos(a, b):
    return np.dot(a, b) / np.linalg.norm(a) / np.linalg.norm(b)


def test_compensation_scoped_and_original_only():
    basis = np.eye(192)
    a, b = matrix([basis[0]]), matrix([basis[1]])
    groups = {
        "q": ("q", "s1", 0, 1, a),
        "n": ("n", "s1", 0, 1, b),
        "other": ("other", "s2", 0, 1, a),
        "null": ("null", "s1", None, 1, a),
    }
    result, neighbors, _, _ = compensate("q", a, groups, "top3")
    assert neighbors == ["n"]
    assert result.shape == (1, 192)
    assert compensate("null", a, groups, "top3")[1] == []
    assert compensate("q", a, groups, "none")[1] == []


def test_end_to_end_mapping_and_cache(tmp_path):
    paths, segments = setup(tmp_path)
    cfg = config(compensation="top3", threshold=None)
    output = tmp_path / "results.jsonl"
    first, meta = run(cfg, paths, output, FakeEncoder())
    assert all(
        r["status"] == "scored_only" and r["predicted_global_speaker_id"] is None
        for r in first
    )
    assert first[0]["compensation_neighbor_ids"] == ["2"]
    assert first[2]["compensation_neighbor_ids"] == []
    assert first[3]["compensation_neighbor_ids"] == []
    assert all(r["best_candidate_id"] == "A" for r in first)
    cfg["scoring"]["threshold"] = first[0]["best_score"]
    cfg["scoring"]["threshold_artifact"] = {
        "threshold": cfg["scoring"]["threshold"],
        "method_id": meta["method_id"],
        "calibration_data_id": "separate-dev",
    }
    second, _ = run(cfg, paths, output, FakeEncoder())
    assert all(r["predicted_global_speaker_id"] == "A" for r in second)
    assert all(r["cache_hit"] for r in second)
    assert all(r["timing_ms"]["embedding"] == 0 for r in second)
    assert len(output.read_text().splitlines()) == 4
    cfg["scoring"]["threshold"] = 2
    cfg["scoring"]["threshold_artifact"]["threshold"] = 2
    third, _ = run(cfg, paths, output, FakeEncoder())
    assert all(r["predicted_global_speaker_id"] == "non_target" for r in third)
    segments[0]["transcript"] = "completely different"
    paths["segments"] = write_jsonl(tmp_path / "segments.jsonl", segments)
    changed, _ = run(cfg, paths, output, FakeEncoder())
    assert changed[0]["candidate_scores"] == third[0]["candidate_scores"]


def test_subsets_empty_gallery_and_bad_provenance(tmp_path):
    paths, segments = setup(tmp_path)
    candidates = tmp_path / "sessions.json"
    candidates.write_text(json.dumps({"clip1": ["B"], "clip2": []}))
    paths["session_candidates"] = str(candidates)
    results, _ = run(
        config(gallery="session_subset"), paths, tmp_path / "out.jsonl", FakeEncoder()
    )
    assert results[0]["best_candidate_id"] == "B"
    assert results[2]["status"] == "empty_gallery"
    segments[0]["diarization_provenance"] = "openrouter-mai-transcribe-2"
    paths["segments"] = write_jsonl(tmp_path / "segments.jsonl", segments)
    with pytest.raises(ValueError, match="selected provider"):
        validate(config(), paths)


def test_selected_diarization_provider_is_required_and_separates_methods(tmp_path):
    paths, segments = setup(tmp_path)
    with pytest.raises(ValueError, match="diarization_provider"):
        validate({k: v for k, v in config().items() if k != "diarization_provider"}, paths)
    _, deepgram_meta = run(config(), paths, tmp_path / "deepgram.jsonl", FakeEncoder())
    for row in segments:
        row["diarization_provenance"] = "openrouter-mai-transcribe-2"
    write_jsonl(Path(paths["segments"]), segments)
    mai_config = config()
    mai_config["diarization_provider"] = "openrouter-mai-transcribe-2"
    _, mai_meta = run(mai_config, paths, tmp_path / "mai.jsonl", FakeEncoder())
    assert mai_meta["diarization_provider"] == "openrouter-mai-transcribe-2"
    assert mai_meta["method_id"] != deepgram_meta["method_id"]


def test_asnorm_cohort_validation_and_execution(tmp_path):
    paths, _ = setup(tmp_path)
    cfg = config("asnorm")
    with pytest.raises(ValueError, match="cohort manifest"):
        validate(cfg, paths)
    audio = Path(
        json.loads(Path(paths["segments"]).read_text().splitlines()[0])["audio_path"]
    )
    checksum = hashlib.sha256(audio.read_bytes()).hexdigest()
    cohort = [
        {
            "audio_path": str(audio),
            "start_s": 0,
            "end_s": 1,
            "speaker_id": f"c{i}",
            "corpus": "synthetic",
            "source_id": f"utt{i}",
            "sha256": checksum,
        }
        for i in range(20)
    ]
    paths["cohort"] = write_jsonl(tmp_path / "cohort.jsonl", cohort)
    results, meta = run(cfg, paths, tmp_path / "out.jsonl", FakeEncoder())
    assert all(np.isfinite(r["best_score"]) for r in results)
    assert meta["cohort_id"] is not None
    cohort[0]["sha256"] = "wrong"
    paths["cohort"] = write_jsonl(tmp_path / "cohort.jsonl", cohort)
    with pytest.raises(ValueError, match="checksum"):
        validate(cfg, paths)


def test_invalid_audio_and_embedding_are_not_unknown(tmp_path):
    paths, segments = setup(tmp_path)
    segments[0]["end_s"] = 100
    paths["segments"] = write_jsonl(tmp_path / "segments.jsonl", segments)
    results, _ = run(config(), paths, tmp_path / "out.jsonl", FakeEncoder())
    assert results[0]["status"] == "invalid_audio"
    assert results[0]["predicted_global_speaker_id"] is None

    class BadEncoder(FakeEncoder):
        fingerprint = "invalid-test"

        def encode(self, waveform):
            if np.mean(waveform) < 0:
                return np.zeros(192)
            return super().encode(waveform)

    audio = tmp_path / "negative.wav"
    sf.write(audio, np.full(16000, -0.5), 16000)
    segments[0].update(audio_path=str(audio), end_s=1)
    paths["segments"] = write_jsonl(tmp_path / "segments.jsonl", segments)
    results, _ = run(config(), paths, tmp_path / "out.jsonl", BadEncoder())
    assert results[0]["status"] == "invalid_embedding"
    assert results[0]["predicted_global_speaker_id"] is None


def test_subsecond_query_is_flagged_but_still_scored(tmp_path):
    paths, segments = setup(tmp_path)
    segments[0]["end_s"] = 0.75
    paths["segments"] = write_jsonl(tmp_path / "segments.jsonl", segments)
    results, metadata = run(config(), paths, tmp_path / "out.jsonl", FakeEncoder())
    assert results[0]["status"] == "scored_only"
    assert results[0]["short_audio_flag"] is True
    assert results[0]["query_window_count"] == 1
    assert results[1]["short_audio_flag"] is False
    assert metadata["short_audio_count"] == 1


def test_pinned_model_uses_only_local_snapshot_weights(tmp_path, monkeypatch):
    snapshot = tmp_path / ("a" * 40)
    snapshot.mkdir()
    for name in (
        "hyperparams.yaml",
        "embedding_model.ckpt",
        "mean_var_norm_emb.ckpt",
        "classifier.ckpt",
        "label_encoder.txt",
    ):
        (snapshot / name).write_bytes(name.encode())
    calls = []

    class Model:
        def eval(self):
            return self

    class Classifier:
        @staticmethod
        def from_hparams(**kwargs):
            calls.append(kwargs)
            return Model()

    torch = types.ModuleType("torch")
    torch.cuda = types.SimpleNamespace(is_available=lambda: False)
    hub = types.ModuleType("huggingface_hub")
    hub.snapshot_download = lambda **kwargs: str(snapshot)
    speechbrain = types.ModuleType("speechbrain")
    speechbrain.__path__ = []
    inference = types.ModuleType("speechbrain.inference")
    inference.__path__ = []
    classifiers = types.ModuleType("speechbrain.inference.classifiers")
    classifiers.EncoderClassifier = Classifier
    for name, module in (
        ("torch", torch),
        ("huggingface_hub", hub),
        ("speechbrain", speechbrain),
        ("speechbrain.inference", inference),
        ("speechbrain.inference.classifiers", classifiers),
    ):
        monkeypatch.setitem(sys.modules, name, module)
    monkeypatch.setattr("tst.encoder.importlib.metadata.version", lambda _: "test")
    encoder = SpeechBrainEncoder(
        {"revision": "a" * 40, "device": "cpu", "offline": True}, tmp_path / "model"
    )
    assert calls[0]["source"] == str(snapshot)
    assert calls[0]["overrides"] == {"pretrained_path": str(snapshot)}
    assert (
        encoder.asset_hashes["embedding_model.ckpt"]
        == hashlib.sha256(b"embedding_model.ckpt").hexdigest()
    )
