# Qwen3.5 4B thinking — baseline prompt preflight — latency

Updated: 2026-09-15T16:00:47+00:00. **Stage/preflight exited successfully; full benchmark not verified**.

All values below are measured milliseconds unless stated otherwise. Empty fields mean unavailable, not zero. Overlapping stages must not be added as end-to-end latency. Cached acquisition, warmup, retries and execution-policy changes remain separate.

Execution policy: **user-authorized concurrent GPU workers with Gemini; latency potentially contended**.

## Memory construction

| Segment | Nodes | Decode | ASR stage | Reasoning | Text embedding | Ready queue | Ordered processing | Admission → checkpoint |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 10 | 3,985.23 | 3.99 | 233,544.07 | 662.70 | 0.10 | 243,895.78 | 247,969.65 |
| 2 | 21 | 6,395.63 | 6.24 | 126,311.36 | 527.62 | 239,478.79 | 134,968.32 | 383,028.57 |
| 3 | 34 | 6,493.12 | 1,301.06 | 162,843.42 | 611.07 | 373,102.37 | 171,446.15 | 554,589.73 |

The two latency columns on the right are unavailable for older serial records. Their original `end_to_end_memory_generation_ms` values remain in the raw audit; they are not silently mixed with pipeline admission-to-checkpoint measurements.

## Preprocessing and graph-update detail

| Segment | Deepgram | MAI | Speech embedding | Face detection | Face clustering | Graph update | ASR cache/precompute |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 2.76 | 1.92 | 1,752.91 | 3,794.66 | 4.70 | 2.89 | False/True |
| 2 | 4.82 | 3.68 | 121.07 | 3,619.85 | 5.78 | 1.96 | False/True |
| 3 | 2.08 | 1,298.69 | 182.03 | 3,335.49 | 6.85 | 4.00 | False/True |

ASR provider times can overlap; the ASR-stage column above is independently measured wall time. An ASR cache hit is not a new provider-speed measurement.

## Per-clip embedding batches

| Segment | Texts | Whole batch ms | Tokens | API attempts |
| --- | --- | --- | --- | --- |
| 1 | 8 | 662.70 | 158 | 1 |
| 2 | 11 | 527.62 | 206 | 1 |
| 3 | 12 | 611.07 | 265 | 1 |

Each input retains its own vector. Individual-text latency is unavailable; batch time is not divided by text count.

## QA measurements

No actual A/B/C/D evaluation rows are available for this run yet. Startup or preflight completion is not a completed 40-trial benchmark.

## ASR outcomes

| Provider | Successful API attempts | Failed attempts | Cache hits |
| --- | --- | --- | --- |
| deepgram-asr | 0 | 0 | 3 |
| openrouter-mai-transcribe-2 | 1 | 0 | 2 |

## Definitions and exact evidence

- [Latency measurement contract](../../scripts/gemini/MEASUREMENT.md)
- [Raw artifacts and logs](../../provenance/raw/qwen_thinking_baseline)

Warm retrieval excludes snapshot/model/index loading and the unrelated startup probe. It includes the actual question embedding, searches, fusion, lookup and reranking. Warmup is recorded separately, and never primes the benchmark question. Provider-internal model residency cannot be controlled.
