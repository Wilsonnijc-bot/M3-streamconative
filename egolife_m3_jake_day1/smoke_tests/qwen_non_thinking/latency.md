# Qwen3.5 4B — non-thinking — latency

Updated: 2026-09-15T03:12:56+00:00. **Stage/preflight exited successfully; full benchmark not verified**.

All values below are measured milliseconds unless stated otherwise. Empty fields mean unavailable, not zero. Overlapping stages must not be added as end-to-end latency. Cached acquisition, warmup, retries and execution-policy changes remain separate.

Execution policy: **user-authorized concurrent GPU workers with Gemini; latency potentially contended**.

## Memory construction

| Segment | Nodes | Decode | ASR stage | Reasoning | Text embedding | Ready queue | Ordered processing | Admission → checkpoint |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 15 | 4,009.20 | 1,820.23 | 22,568.71 | 577.01 | 0.13 | 32,819.35 | 38,732.30 |
| 2 | 24 | 5,392.12 | 9,464.00 | 16,363.13 | 460.02 | 21,776.57 | 26,489.30 | 65,318.82 |

The two latency columns on the right are unavailable for older serial records. Their original `end_to_end_memory_generation_ms` values remain in the raw audit; they are not silently mixed with pipeline admission-to-checkpoint measurements.

## Preprocessing and graph-update detail

| Segment | Deepgram | MAI | Speech embedding | Face detection | Face clustering | Graph update | ASR cache/precompute |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 1,819.17 | 883.23 | 1,705.22 | 3,858.54 | 4.22 | 2.64 | False/True |
| 2 | 9,463.07 | 2,476.83 | 137.05 | 3,566.18 | 6.52 | 2.47 | False/True |

ASR provider times can overlap; the ASR-stage column above is independently measured wall time. An ASR cache hit is not a new provider-speed measurement.

## Per-clip embedding batches

| Segment | Texts | Whole batch ms | Tokens | API attempts |
| --- | --- | --- | --- | --- |
| 1 | 13 | 577.01 | 215 | 1 |
| 2 | 10 | 460.02 | 153 | 1 |

Each input retains its own vector. Individual-text latency is unavailable; batch time is not divided by text count.

## QA measurements

No actual A/B/C/D evaluation rows are available for this run yet. Startup or preflight completion is not a completed 40-trial benchmark.

## ASR outcomes

| Provider | Successful API attempts | Failed attempts | Cache hits |
| --- | --- | --- | --- |
| deepgram-asr | 3 | 0 | 0 |
| openrouter-mai-transcribe-2 | 2 | 1 | 0 |

## Definitions and exact evidence

- [Latency measurement contract](../../scripts/gemini/MEASUREMENT.md)
- [Raw artifacts and logs](../../provenance/raw/qwen_non_thinking)

Warm retrieval excludes snapshot/model/index loading and the unrelated startup probe. It includes the actual question embedding, searches, fusion, lookup and reranking. Warmup is recorded separately, and never primes the benchmark question. Provider-internal model residency cannot be controlled.
