# Qwen3.5 4B — identity prompt v2 — latency

Updated: 2026-09-15T16:00:47+00:00. **Stopped after failure; incomplete benchmark**.

All values below are measured milliseconds unless stated otherwise. Empty fields mean unavailable, not zero. Overlapping stages must not be added as end-to-end latency. Cached acquisition, warmup, retries and execution-policy changes remain separate.

Execution policy: **user-authorized concurrent GPU workers with Gemini; latency potentially contended**.

## Memory construction

| Segment | Nodes | Decode | ASR stage | Reasoning | Text embedding | Ready queue | Ordered processing | Admission → checkpoint |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 13 | 3,404.24 | 2.89 | 152,006.79 | 674.87 | 0.08 | 162,462.58 | 165,950.07 |
| 2 | 22 | 5,508.62 | 4.77 | 138,828.73 | 1,016.65 | 158,392.20 | 147,620.28 | 313,665.93 |

The two latency columns on the right are unavailable for older serial records. Their original `end_to_end_memory_generation_ms` values remain in the raw audit; they are not silently mixed with pipeline admission-to-checkpoint measurements.

## Preprocessing and graph-update detail

| Segment | Deepgram | MAI | Speech embedding | Face detection | Face clustering | Graph update | ASR cache/precompute |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 2.00 | 1.86 | 1,851.61 | 3,786.65 | 4.13 | 3.39 | False/True |
| 2 | 3.56 | 3.69 | 107.93 | 3,077.24 | 248.40 | 2.38 | False/True |

ASR provider times can overlap; the ASR-stage column above is independently measured wall time. An ASR cache hit is not a new provider-speed measurement.

## Per-clip embedding batches

| Segment | Texts | Whole batch ms | Tokens | API attempts |
| --- | --- | --- | --- | --- |
| 1 | 11 | 674.87 | 199 | 1 |
| 2 | 9 | 1,016.65 | 150 | 1 |

Each input retains its own vector. Individual-text latency is unavailable; batch time is not divided by text count.

## QA measurements

No actual A/B/C/D evaluation rows are available for this run yet. Startup or preflight completion is not a completed 40-trial benchmark.

## ASR outcomes

| Provider | Successful API attempts | Failed attempts | Cache hits |
| --- | --- | --- | --- |
| deepgram-asr | 0 | 0 | 2 |
| openrouter-mai-transcribe-2 | 0 | 0 | 2 |

## Definitions and exact evidence

- [Latency measurement contract](../../scripts/gemini/MEASUREMENT.md)
- [Raw artifacts and logs](../../provenance/raw/qwen_identity_v2)

Warm retrieval excludes snapshot/model/index loading and the unrelated startup probe. It includes the actual question embedding, searches, fusion, lookup and reranking. Warmup is recorded separately, and never primes the benchmark question. Provider-internal model residency cannot be controlled.
