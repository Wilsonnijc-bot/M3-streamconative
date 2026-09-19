"""Standalone offline TST runner. No imports from graph, ASR, or memory code."""

import argparse
import hashlib
import json
import math
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

from .audio import AudioExtractor, EmbeddingError, file_hash
from .encoder import SpeechBrainEncoder
from .scoring import cohort_stats, compensate, matrix, score, unit


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def records(path):
    with open(path, encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if line.strip():
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise ValueError(f"{path}:{line_number}: expected object")
                yield value


def read_config(path):
    text = Path(path).read_text(encoding="utf-8")
    if Path(path).suffix in (".yaml", ".yml"):
        import yaml

        return yaml.safe_load(text)
    return json.loads(text)


def resolve_ref(row, manifest):
    item = dict(row)
    path = Path(item["audio_path"])
    item["audio_path"] = str(
        (Path(manifest).parent / path).resolve() if not path.is_absolute() else path
    )
    for key in ("start_s", "end_s"):
        value = item[key]
        if (
            isinstance(value, bool)
            or not isinstance(value, (float, int))
            or not math.isfinite(value)
        ):
            raise ValueError(f"invalid {key}")
    if item["start_s"] < 0 or item["end_s"] <= item["start_s"]:
        raise ValueError("invalid audio interval")
    if not Path(item["audio_path"]).is_file():
        raise ValueError(f"missing audio: {item['audio_path']}")
    return item


def validate(config, paths):
    provider = config.get("diarization_provider")
    if not isinstance(provider, str) or not provider.strip() or provider != provider.strip():
        raise ValueError("configure one nonempty diarization_provider")
    if config["encoder"]["model_id"] != "speechbrain/spkrec-ecapa-voxceleb":
        raise ValueError("unsupported encoder")
    revision = config["encoder"].get("revision")
    if (
        not isinstance(revision, str)
        or len(revision) != 40
        or any(c not in "0123456789abcdef" for c in revision)
    ):
        raise ValueError(
            "encoder revision must be a 40-character immutable commit hash"
        )
    if config["encoder"].get("expected_embedding_dim", 192) != 192:
        raise ValueError("expected ECAPA embedding dimension is 192")
    if config["gallery"]["policy"] not in ("all_enrolled", "session_subset"):
        raise ValueError("unknown gallery policy")
    if config["scoring"]["normalization"] not in ("cosine", "asnorm"):
        raise ValueError("unknown normalization")
    if config["compensation"]["mode"] not in ("none", "top1", "top2", "top3"):
        raise ValueError("unknown compensation mode")
    if (
        config["compensation"].get("profile", "short4_equal_segment_mean_v1")
        != "short4_equal_segment_mean_v1"
    ):
        raise ValueError("unsupported compensation profile")
    threshold = config["scoring"].get("threshold")
    if threshold is not None and (
        isinstance(threshold, bool)
        or not isinstance(threshold, (float, int))
        or not math.isfinite(threshold)
    ):
        raise ValueError("threshold must be finite")
    if threshold is not None and not isinstance(
        config["scoring"].get("threshold_artifact"), dict
    ):
        raise ValueError(
            "mapping requires threshold_artifact with calibration provenance"
        )
    minimum = config["encoder"].get("minimum_samples", 0)
    if isinstance(minimum, bool) or not isinstance(minimum, int) or minimum < 0:
        raise ValueError("minimum_samples must be a nonnegative integer")
    audio = config.get("audio", {})
    for key, expected in (
        ("sample_rate", 16000),
        ("channel_policy", "first"),
        ("window_s", 4.0),
        ("shift_s", 1.5),
        ("tail_policy", "end_aligned_unique"),
        ("short_policy", "native_length_then_minimum_zero_pad"),
        ("boundary_margin_s", 0.0),
    ):
        if audio.get(key, expected) != expected:
            raise ValueError(f"unsupported audio policy: {key}")
    if config.get("runtime", {}).get("device", "cpu") != "cpu" and not config[
        "runtime"
    ]["device"].startswith("cuda"):
        raise ValueError("device must be cpu or cuda")

    segments = [resolve_ref(r, paths["segments"]) for r in records(paths["segments"])]
    enrollment = [
        resolve_ref(r, paths["enrollment"]) for r in records(paths["enrollment"])
    ]
    if not enrollment:
        raise ValueError("enrollment manifest is empty")
    ids = [r["segment_id"] for r in segments]
    if any(not isinstance(s, str) or not s for s in ids) or len(ids) != len(set(ids)):
        raise ValueError("segment IDs must be nonempty and unique")
    for row in segments:
        if not all(
            isinstance(row.get(k), str) and row[k] for k in ("session_id", "clip_id")
        ):
            raise ValueError("segment requires explicit session_id and clip_id")
        if row.get("diarization_provenance") != provider:
            raise ValueError("segment diarization provenance must match selected provider")
        if row.get("timestamp_precision") not in ("raw", "rounded"):
            raise ValueError("declare timestamp_precision: raw or rounded")
    for row in enrollment:
        if not all(
            row.get(k)
            for k in ("global_speaker_id", "source_id", "verification_provenance")
        ):
            raise ValueError(
                "enrollment requires ID, source_id, verification_provenance"
            )
    global_ids = {r["global_speaker_id"] for r in enrollment}
    if "non_target" in global_ids or not all(
        isinstance(g, str) and g for g in global_ids
    ):
        raise ValueError("invalid enrolled identity")
    gallery = {}
    if config["gallery"]["policy"] == "session_subset":
        if not paths.get("session_candidates"):
            raise ValueError("session_subset requires session candidates manifest")
        gallery = json.loads(Path(paths["session_candidates"]).read_text())
        if (
            not isinstance(gallery, dict)
            or {r["session_id"] for r in segments} - gallery.keys()
        ):
            raise ValueError("candidate gallery missing sessions")
        for session, candidates in gallery.items():
            if (
                not isinstance(candidates, list)
                or any(not isinstance(g, str) for g in candidates)
                or len(set(candidates)) != len(candidates)
                or set(candidates) - global_ids
            ):
                raise ValueError(f"invalid session gallery: {session}")
    cohort = []
    cconfig = config.get("cohort", {})
    if config["scoring"]["normalization"] == "asnorm":
        if not paths.get("cohort"):
            raise ValueError("AS-Norm requires cohort manifest")
        cohort = [resolve_ref(r, paths["cohort"]) for r in records(paths["cohort"])]
        if cconfig.get("corpus", "VoxBlink2") != "VoxBlink2" and not cconfig.get(
            "approximate", False
        ):
            raise ValueError("strict cohort requires VoxBlink2")
        speakers = {r["speaker_id"] for r in cohort}
        expected = cconfig.get("speaker_count", 2000)
        if (
            not isinstance(expected, int)
            or expected < 20
            or (expected != 2000 and not cconfig.get("approximate", False))
        ):
            raise ValueError("strict cohort requires exactly 2000 speakers")
        if len(speakers) != expected or not cohort:
            raise ValueError("cohort speaker count mismatch")
        if (
            cconfig.get("representation", "speaker_centroid_v1")
            != "speaker_centroid_v1"
            or cconfig.get("adaptive_k", 20) != 20
            or cconfig.get("std_ddof", 0) != 0
            or cconfig.get("std_floor", 1e-6) != 1e-6
        ):
            raise ValueError("unsupported AS-Norm convention")
        if "seed" not in cconfig or not isinstance(cconfig["seed"], int):
            raise ValueError("cohort selection seed required")
        checked_audio = {}
        for row in cohort:
            if (
                not all(
                    isinstance(row.get(k), str) and row[k]
                    for k in ("source_id", "sha256", "speaker_id")
                )
                or row["speaker_id"] in global_ids
                or row.get("corpus") != cconfig.get("corpus", "VoxBlink2")
            ):
                raise ValueError(
                    "cohort requires source IDs and checksums, separate from enrollment IDs"
                )
            if row["audio_path"] not in checked_audio:
                checked_audio[row["audio_path"]] = file_hash(row["audio_path"])
            actual_hash = checked_audio[row["audio_path"]]
            if actual_hash != row["sha256"]:
                raise ValueError(f"cohort checksum mismatch: {row['audio_path']}")
    return segments, enrollment, cohort, gallery


def run(config, paths, output, encoder=None):
    segments, enrollment, cohort_refs, session_galleries = validate(config, paths)
    started = time.perf_counter()
    runtime = config.get("runtime", {})
    cache = Path(runtime.get("cache_dir", Path(output).parent / "tst_cache"))
    cache.mkdir(parents=True, exist_ok=True)
    load_start = time.perf_counter()
    encoder = encoder or SpeechBrainEncoder(
        {
            "revision": config["encoder"]["revision"],
            "device": runtime.get("device", "cpu"),
            "offline": runtime.get("offline", False),
        },
        cache / "model",
    )
    model_ms = (time.perf_counter() - load_start) * 1000
    if getattr(encoder, "revision", None) != config["encoder"]["revision"]:
        raise ValueError("encoder revision mismatch")
    extractor = AudioExtractor(
        encoder,
        encoder.fingerprint,
        cache / "ecapa_embeddings",
        config["encoder"].get("minimum_samples", 0),
    )
    preparation = time.perf_counter()
    gallery_vectors = defaultdict(list)
    for row in enrollment:
        vectors, _, _ = extractor.extract(row)
        gallery_vectors[row["global_speaker_id"]].extend(vectors)
    gallery_vectors = {g: matrix(v) for g, v in gallery_vectors.items()}
    cohort_vectors = None
    if cohort_refs:
        grouped = defaultdict(list)
        for row in cohort_refs:
            vectors, _, _ = extractor.extract(row)
            grouped[row["speaker_id"]].extend(vectors)
        cohort_vectors = matrix(
            [unit(np.mean(grouped[g], axis=0)) for g in sorted(grouped)]
        )
    preparation_ms = (time.perf_counter() - preparation) * 1000
    preparation_cache_hits = extractor.cache_hits
    normalization = config["scoring"]["normalization"]
    enrollment_stats = (
        {g: cohort_stats(v, cohort_vectors) for g, v in gallery_vectors.items()}
        if cohort_vectors is not None
        else {}
    )
    gallery_id = digest(
        {
            "policy": config["gallery"]["policy"],
            "candidates": session_galleries,
            "enrollment": file_hash(paths["enrollment"]),
        }
    )
    cohort_id = (
        digest({"manifest": file_hash(paths["cohort"]), "settings": config["cohort"]})
        if cohort_refs
        else None
    )
    method_id = digest(
        {
            "diarization_provider": config["diarization_provider"],
            "encoder": encoder.fingerprint,
            "normalization": normalization,
            "gallery": gallery_id,
            "cohort": cohort_id,
            "compensation": {
                "mode": config["compensation"]["mode"],
                "profile": "short4_equal_segment_mean_v1",
            },
        }
    )
    threshold = config["scoring"].get("threshold")
    artifact = config["scoring"].get("threshold_artifact")
    if threshold is not None:
        if not artifact:
            raise ValueError(
                "mapping requires threshold_artifact with calibration provenance"
            )
        for key, expected in (("method_id", method_id), ("threshold", threshold)):
            if artifact.get(key) != expected:
                raise ValueError(f"threshold artifact {key} mismatch")
        if not artifact.get("calibration_data_id"):
            raise ValueError("threshold calibration data ID required")

    originals = {}
    errors = {}
    embeddings_ms = {}
    cache_hit = {}
    for row in segments:
        sid = row["segment_id"]
        try:
            originals[sid], cache_hit[sid], embeddings_ms[sid] = extractor.extract(row)
        except (ValueError, OSError, RuntimeError) as exc:
            errors[sid] = (
                "invalid_embedding"
                if isinstance(exc, EmbeddingError)
                else "invalid_audio",
                str(exc),
            )
            originals[sid] = None
            embeddings_ms[sid] = 0.0
            cache_hit[sid] = False
    groups = {
        r["segment_id"]: (
            r["segment_id"],
            r["session_id"],
            r.get("local_speaker_id"),
            r["end_s"] - r["start_s"],
            originals[r["segment_id"]],
        )
        for r in segments
    }
    results = []
    for row in segments:
        began = time.perf_counter()
        sid = row["segment_id"]
        candidate_ids = sorted(
            session_galleries[row["session_id"]]
            if session_galleries
            else gallery_vectors
        )
        result = {
            k: row.get(k)
            for k in (
                "session_id",
                "clip_id",
                "segment_id",
                "audio_path",
                "start_s",
                "end_s",
                "local_speaker_id",
                "transcript",
                "diarization_provenance",
                "timestamp_precision",
            )
        }
        result.update(
            status=None,
            predicted_global_speaker_id=None,
            best_candidate_id=None,
            best_score=None,
            threshold=threshold,
            candidate_scores={},
            compensation_neighbor_ids=[],
            compensation_neighbor_similarities=[],
            compensation_fallback=None,
            short_audio_flag=(row["end_s"] - row["start_s"] < 1.0),
            query_window_count=0,
            effective_embedding_count=0,
            method_id=method_id,
            gallery_id=gallery_id,
            cohort_id=cohort_id,
            encoder_fingerprint=encoder.fingerprint,
            cache_hit=cache_hit[sid],
            error=None,
            asnorm_std_floor_count=0,
        )
        comp_ms = score_ms = 0.0
        if sid in errors:
            result["status"], result["error"] = errors[sid]
        elif not candidate_ids:
            result["status"] = "empty_gallery"
            result["query_window_count"] = len(originals[sid])
        else:
            query = originals[sid]
            result["query_window_count"] = len(query)
            t = time.perf_counter()
            query, neighbors, similarities, fallback = compensate(
                sid, query, groups, config["compensation"]["mode"]
            )
            comp_ms = (time.perf_counter() - t) * 1000
            result["compensation_neighbor_ids"] = neighbors
            result["compensation_neighbor_similarities"] = similarities
            result["compensation_fallback"] = fallback
            result["effective_embedding_count"] = len(query)
            t = time.perf_counter()
            query_stats = (
                cohort_stats(query, cohort_vectors)
                if cohort_vectors is not None
                else None
            )
            if query_stats is not None:
                result["asnorm_std_floor_count"] = query_stats[2]
            for g in candidate_ids:
                value, floors = score(
                    gallery_vectors[g],
                    query,
                    normalization,
                    cohort_vectors,
                    enrollment_stats.get(g),
                    query_stats,
                )
                result["candidate_scores"][g] = value
                result["asnorm_std_floor_count"] += floors - (
                    query_stats[2] if query_stats else 0
                )
            score_ms = (time.perf_counter() - t) * 1000
            best = min(candidate_ids, key=lambda g: (-result["candidate_scores"][g], g))
            result["best_candidate_id"] = best
            result["best_score"] = result["candidate_scores"][best]
            result["status"] = "scored_only" if threshold is None else "mapped"
            if threshold is not None:
                result["predicted_global_speaker_id"] = (
                    best if result["best_score"] >= threshold else "non_target"
                )
        result["timing_ms"] = {
            "embedding": embeddings_ms[sid],
            "compensation": comp_ms,
            "scoring": score_ms,
            "mapping_total": (time.perf_counter() - began) * 1000 + embeddings_ms[sid],
        }
        results.append(result)

    metadata = {
        "description": "paper-informed mapping algorithm using a standard pretrained ECAPA-TDNN",
        "diarization_provider": config["diarization_provider"],
        "config": config,
        "method_id": method_id,
        "gallery_id": gallery_id,
        "cohort_id": cohort_id,
        "encoder_fingerprint": encoder.fingerprint,
        "encoder_revision": encoder.revision,
        "checkpoint_sha256": encoder.checkpoint_hash,
        "preprocessing_sha256": encoder.preprocessing_hash,
        "model_asset_hashes": getattr(encoder, "asset_hashes", None),
        "package_versions": encoder.versions,
        "preprocessing": {
            "sample_rate": 16000,
            "channel": "first",
            "resampler": "scipy.signal.resample_poly",
            "minimum_samples": extractor.minimum_samples,
            "padded_windows": extractor.padded_windows,
        },
        "manifest_hashes": {k: file_hash(v) for k, v in paths.items() if v},
        "timing_ms": {
            "model_load": model_ms,
            "enrollment_cohort_preparation": preparation_ms,
            "fresh_query_embedding_total": sum(embeddings_ms.values()),
            "compensation_total": sum(r["timing_ms"]["compensation"] for r in results),
            "scoring_total": sum(r["timing_ms"]["scoring"] for r in results),
            "mapping_total": (time.perf_counter() - started) * 1000,
        },
        "cache_hits": extractor.cache_hits,
        "preparation_cache_hits": preparation_cache_hits,
        "segment_cache_hits": sum(cache_hit.values()),
        "segment_count": len(results),
        "short_audio_count": sum(r["short_audio_flag"] for r in results),
    }
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as stream:
        for item in results:
            stream.write(json.dumps(item, ensure_ascii=False, allow_nan=False) + "\n")
    output.with_suffix(output.suffix + ".run.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return results, metadata


def main():
    parser = argparse.ArgumentParser(
        description="Offline ECAPA TST mapping; no graph writes"
    )
    for name in ("config", "segments", "enrollment", "output"):
        parser.add_argument("--" + name.replace("_", "-"), required=True)
    parser.add_argument("--cohort")
    parser.add_argument("--session-candidates")
    args = parser.parse_args()
    paths = {
        k: getattr(args, k)
        for k in ("segments", "enrollment", "cohort", "session_candidates")
    }
    run(read_config(args.config), paths, args.output)


if __name__ == "__main__":
    main()
