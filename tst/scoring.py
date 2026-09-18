"""Versioned score-level TST conventions from TST_ALGORITHM_SPEC.md."""

import numpy as np


def unit(vector):
    vector = np.asarray(vector, dtype=np.float64)
    norm = np.linalg.norm(vector)
    if not np.all(np.isfinite(vector)) or not np.isfinite(norm) or norm <= 1e-12:
        raise ValueError("non-finite or zero-norm embedding")
    return vector / norm


def matrix(rows, dim=192):
    value = np.asarray(rows, dtype=np.float64)
    if value.ndim != 2 or value.shape[0] == 0 or value.shape[1] != dim:
        raise ValueError(f"expected nonempty embedding matrix with dimension {dim}")
    return np.stack([unit(row) for row in value])


def cohort_stats(vectors, cohort, k=20, floor=1e-6):
    similarities = vectors @ cohort.T
    top = np.partition(similarities, -k, axis=1)[:, -k:]
    mean = top.mean(axis=1)
    std = top.std(axis=1, ddof=0)
    return mean, np.maximum(std, floor), int(np.count_nonzero(std < floor))


def score(
    enrollment,
    query,
    normalization="cosine",
    cohort=None,
    enrollment_stats=None,
    query_stats=None,
    k=20,
    floor=1e-6,
):
    trials = enrollment @ query.T
    if normalization == "cosine":
        return float(trials.mean()), 0
    if normalization != "asnorm" or cohort is None:
        raise ValueError("AS-Norm requires a cohort")
    em, es, ec = (
        enrollment_stats
        if enrollment_stats is not None
        else cohort_stats(enrollment, cohort, k, floor)
    )
    qm, qs, qc = (
        query_stats
        if query_stats is not None
        else cohort_stats(query, cohort, k, floor)
    )
    normalized = 0.5 * (
        (trials - em[:, None]) / es[:, None] + (trials - qm[None, :]) / qs[None, :]
    )
    return float(normalized.mean()), ec + qc


def compensate(query_id, query, segments, mode, profile="short4_equal_segment_mean_v1"):
    """segments contains (id, session, local label, duration, original matrix)."""
    if profile != "short4_equal_segment_mean_v1":
        raise ValueError("unknown compensation profile")
    current = segments[query_id]
    count = {"none": 0, "top1": 1, "top2": 2, "top3": 3}[mode]
    if not count or current[3] >= 4 or current[2] is None:
        return query, [], [], None
    neighbors = []
    for sid, (ident, session, label, _, vectors) in segments.items():
        if (
            sid != query_id
            and session == current[1]
            and label == current[2]
            and vectors is not None
        ):
            neighbors.append((float((query @ vectors.T).mean()), sid, vectors))
    neighbors.sort(key=lambda row: (-row[0], row[1]))
    selected = neighbors[:count]
    if not selected:
        return query, [], [], None
    try:
        combined = unit(
            np.mean(
                [unit(v.mean(axis=0)) for v in [query] + [n[2] for n in selected]],
                axis=0,
            )
        )
    except ValueError:
        return query, [], [], "invalid_compensation_mean"
    return combined[None, :], [n[1] for n in selected], [n[0] for n in selected], None
