# Bedroom first-segment functional preflight — latency

Updated: 2026-09-15T02:19:42+00:00. **Functional preflight passed: all four methods**.

All values below are measured milliseconds unless stated otherwise. Empty fields mean unavailable, not zero. Overlapping stages must not be added as end-to-end latency. Cached acquisition, warmup, retries and execution-policy changes remain separate.

## QA measurements

| Q | Method | Mode | Retrieval requests | Reasoning calls | Retrieval total | Reasoning total | Question → answer | Answer | Correct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | A | warm_retrieval_uncached_question | 1 | 2 | 601.06 | 16,971.99 | 17,573.79 | A young woman enters a bedroom, takes off her outdoor winter jacket and baseball cap, hangs them on a coat rack, and places her backpack on the bed. | — |
| 1 | B | warm_retrieval_uncached_question | 1 | 1 | 332.45 | 4,885.24 | 5,218.10 | A young woman arriving indoors, walking through her apartment, and shedding her outdoor winter layers (removing and hanging up her black jacket and cap, and handling her backpack). | — |
| 1 | C | warm_retrieval_uncached_question | 1 | 1 | 269.71 | 4,648.03 | 4,918.09 | A young woman is arriving indoors, walking through an apartment, and shedding her outdoor winter layers (removing her jacket and baseball cap, and setting down her backpack). | — |
| 1 | D | warm_retrieval_uncached_question | 1 | 1 | 1,445.08 | 5,125.67 | 6,571.57 | A young woman is walking through the apartment and entering a bedroom from the hallway. | — |

### Retrieval-stage detail

| Q/method/round | Embedding | Dense | Sparse | StreamMeCo scoring | Fusion | Lookup | Rerank | Total |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1/A/1 | 598.04 | 2.72 | 0.00 | 0.01 | — | 0.09 | 0.00 | 601.06 |
| 1/B/1 | 329.79 | 2.36 | 0.00 | 0.01 | — | 0.11 | 0.00 | 332.45 |
| 1/C/1 | 267.75 | 1.77 | 0.00 | 0.01 | — | 0.06 | 0.00 | 269.71 |
| 1/D/1 | 679.40 | 3.88 | 14.87 | 0.00 | 0.19 | 0.04 | 755.66 | 1,445.08 |

### Reasoning calls

| Q/method/call | Purpose | Latency | Input tokens | Output tokens |
| --- | --- | --- | --- | --- |
| 1/A/1 | controller | 4,664.27 | 1238 | 223 |
| 1/A/2 | controller | 12,307.72 | 1470 | 441 |
| 1/B/1 | final_answer | 4,885.24 | 208 | 256 |
| 1/C/1 | final_answer | 4,648.03 | 174 | 316 |
| 1/D/1 | final_answer | 5,125.67 | 839 | 195 |

## Excluded setup / warmup

| Q | Method | Snapshot load | Warmup | Status |
| --- | --- | --- | --- | --- |
| 1 | A | 1.57 | 488.55 | success |
| 1 | B | 1.59 | 683.83 | success |
| 1 | C | 1.27 | 491.58 | success |
| 1 | D | 4.18 | 5,484.00 | success |

These are excluded from timed QA calls and warm retrieval latency.

## Definitions and exact evidence

- [Latency measurement contract](../../scripts/MEASUREMENT.md)
- [Raw artifacts and logs](../../provenance/raw/preflight)

Warm retrieval excludes snapshot/model/index loading and the unrelated startup probe. It includes the actual question embedding, searches, fusion, lookup and reranking. Warmup is recorded separately, and never primes the benchmark question. Provider-internal model residency cannot be controlled.
