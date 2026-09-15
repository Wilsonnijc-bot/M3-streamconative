# First-clip model comparison — Hyperstack — latency

Updated: 2026-09-15T03:12:56+00:00. **Saved diagnostic/preflight artifacts; full benchmark not verified**.

All values below are measured milliseconds unless stated otherwise. Empty fields mean unavailable, not zero. Overlapping stages must not be added as end-to-end latency. Cached acquisition, warmup, retries and execution-policy changes remain separate.

## First-clip construction comparison

| Model | Total construction | VLM | Text embedding | Graph update |
| --- | --- | --- | --- | --- |
| qwen3.5-4b | 131,310.04 | 111,703.85 | 1,059.59 | 0.16 |
| gemini-3.8-flash | 32,339.18 | 12,124.97 | 1,666.47 | 0.47 |

## QA measurements

No actual A/B/C/D evaluation rows are available for this run yet. Startup or preflight completion is not a completed 40-trial benchmark.

## Definitions and exact evidence

- [Latency measurement contract](../../scripts/gemini/MEASUREMENT.md)
- [Raw artifacts and logs](../../provenance/raw/first_clip_hyperstack)

Warm retrieval excludes snapshot/model/index loading and the unrelated startup probe. It includes the actual question embedding, searches, fusion, lookup and reranking. Warmup is recorded separately, and never primes the benchmark question. Provider-internal model residency cannot be controlled.
