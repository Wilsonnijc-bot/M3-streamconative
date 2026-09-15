# First-clip model comparison — OpenRouter — latency

Updated: 2026-09-15T03:12:56+00:00. **Saved diagnostic/preflight artifacts; full benchmark not verified**.

All values below are measured milliseconds unless stated otherwise. Empty fields mean unavailable, not zero. Overlapping stages must not be added as end-to-end latency. Cached acquisition, warmup, retries and execution-policy changes remain separate.

## First-clip construction comparison

| Model | Total construction | VLM | Text embedding | Graph update |
| --- | --- | --- | --- | --- |
| qwen3.5-4b | 133,169.57 | 107,613.76 | 3,834.57 | 0.18 |
| gemini-3.8-flash | 52,006.62 | 25,485.34 | 4,799.15 | 0.46 |

## QA measurements

No actual A/B/C/D evaluation rows are available for this run yet. Startup or preflight completion is not a completed 40-trial benchmark.

## Definitions and exact evidence

- [Latency measurement contract](../../scripts/gemini/MEASUREMENT.md)
- [Raw artifacts and logs](../../provenance/raw/first_clip_openrouter)

Warm retrieval excludes snapshot/model/index loading and the unrelated startup probe. It includes the actual question embedding, searches, fusion, lookup and reranking. Warmup is recorded separately, and never primes the benchmark question. Provider-internal model residency cannot be controlled.
