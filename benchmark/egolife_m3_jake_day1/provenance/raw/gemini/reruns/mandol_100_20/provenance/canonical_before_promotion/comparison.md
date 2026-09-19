# Jake DAY1 — Gemini first ten questions

Reasoning: `gemini-3.8-flash` via 302.ai. A/B/C use M3 native OpenRouter text-embedding-3-large; D independently embeds exported text with 302.ai Qwen3-Embedding-0.6B (1024D), local original SPLADE and BM25, then Qwen3-Reranker-0.6B.

All QA rows measure warm local retrieval with an uncached question. Snapshot loading, offline adaptation/compression, and fixed neutral-probe warmup are excluded and recorded in retrieval_warmup.jsonl. Actual query embeddings, searches and reranking remain timed; cloud-provider internal model state is not controlled. Mandol backend times include nested embeddings and unit lookup; parallel/nested timings are not additive. Retrieval total is measured wall time. TTFT is unavailable for the non-streaming API. Compression and adaptor use zero reasoning calls.

| Latency mode | Skipped segments | ASR degraded segments | Q | Method | Memory nodes | Retrieval queries | Gemini calls | Embed ms | Dense ms | Sparse ms | StreamMeCo/Mandol ms | Graph lookup ms | Rerank ms | Retrieval total ms | Gemini answer/controller ms | End-to-end ms | Answer | Correct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| warm_retrieval_uncached_question | 0 | 0 | 1 | A | 271 | 4 | 6 | 1332.94 | 112.55 | 0.00 | 0.86 | 0.89 | 0.00 | 1448.99 | 49965.25 | 51417.21 | C | False |
| warm_retrieval_uncached_question | 0 | 0 | 1 | B | 271 | 1 | 1 | 262.03 | 26.05 | 0.00 | 0.20 | 0.43 | 0.00 | 289.06 | 51161.24 | 51450.96 | D | False |
| warm_retrieval_uncached_question | 0 | 0 | 1 | C | 216 | 1 | 1 | 308.96 | 22.07 | 0.00 | 0.16 | 0.42 | 0.00 | 332.00 | 15364.40 | 15697.15 | D | False |
| warm_retrieval_uncached_question | 0 | 0 | 1 | D | 271 | 1 | 1 | 698.11 | 4.56 | 19.85 | 0.30 | 0.27 | 862.48 | 1569.40 | 17248.99 | 18819.50 | D | False |
| warm_retrieval_uncached_question | 0 | 0 | 2 | A | 606 | 4 | 6 | 1253.41 | 242.96 | 0.00 | 2.20 | 1.86 | 0.00 | 1502.91 | 58206.15 | 59712.18 | C | True |
| warm_retrieval_uncached_question | 0 | 0 | 2 | B | 606 | 1 | 1 | 260.28 | 63.05 | 0.00 | 0.67 | 0.71 | 0.00 | 325.21 | 13301.95 | 13627.75 | B | False |
| warm_retrieval_uncached_question | 0 | 0 | 2 | C | 485 | 1 | 1 | 350.45 | 45.92 | 0.00 | 0.47 | 0.77 | 0.00 | 398.26 | 59648.16 | 60047.06 | C | True |
| warm_retrieval_uncached_question | 0 | 0 | 2 | D | 606 | 1 | 1 | 690.84 | 3.90 | 19.02 | 0.20 | 0.32 | 828.14 | 1526.73 | 31382.77 | 32910.13 | B | False |
| warm_retrieval_uncached_question | 0 | 0 | 3 | A | 614 | 4 | 6 | 2021.66 | 236.85 | 0.00 | 2.10 | 1.91 | 0.00 | 2265.06 | 88471.81 | 90739.85 | A | False |
| warm_retrieval_uncached_question | 0 | 0 | 3 | B | 614 | 1 | 1 | 593.55 | 63.38 | 0.00 | 0.48 | 0.71 | 0.00 | 658.61 | 20580.24 | 21239.40 | B | False |
| warm_retrieval_uncached_question | 0 | 0 | 3 | C | 491 | 1 | 1 | 504.69 | 45.76 | 0.00 | 0.44 | 0.62 | 0.00 | 552.08 | 14600.32 | 15152.97 | D | True |
| warm_retrieval_uncached_question | 0 | 0 | 3 | D | 614 | 1 | 1 | 668.29 | 4.41 | 18.99 | 0.25 | 0.32 | 864.84 | 1544.49 | 23146.09 | 24691.20 | B | False |
| warm_retrieval_uncached_question | 0 | 0 | 4 | A | 808 | 4 | 6 | 1496.23 | 331.72 | 0.00 | 3.10 | 2.76 | 0.00 | 1836.28 | 128827.30 | 130666.79 | B | False |
| warm_retrieval_uncached_question | 0 | 0 | 4 | B | 808 | 1 | 1 | 412.77 | 79.43 | 0.00 | 0.71 | 0.89 | 0.00 | 494.40 | 63205.99 | 63700.92 | C | True |
| warm_retrieval_uncached_question | 0 | 0 | 4 | C | 646 | 1 | 1 | 228.95 | 65.69 | 0.00 | 0.62 | 0.79 | 0.00 | 296.67 | 12973.60 | 13270.92 | C | True |
| warm_retrieval_uncached_question | 0 | 0 | 4 | D | 808 | 1 | 1 | 622.60 | 1.69 | 19.03 | 0.26 | 0.32 | 832.03 | 1463.58 | 8192.75 | 9656.90 | C | True |
| warm_retrieval_uncached_question | 0 | 1 | 5 | A | 1139 | 4 | 6 | 1404.86 | 778.50 | 0.00 | 6.71 | 4.09 | 0.00 | 2197.30 | 46680.52 | 48881.10 | A | False |
| warm_retrieval_uncached_question | 0 | 1 | 5 | B | 1139 | 1 | 1 | 221.17 | 114.28 | 0.00 | 1.03 | 1.24 | 0.00 | 338.44 | 154403.76 | 154742.74 | A | False |
| warm_retrieval_uncached_question | 0 | 1 | 5 | C | 908 | 1 | 1 | 219.35 | 79.04 | 0.00 | 0.83 | 1.08 | 0.00 | 300.97 | 12379.97 | 12681.49 | A | False |
| warm_retrieval_uncached_question | 0 | 1 | 5 | D | 1139 | 1 | 1 | 616.35 | 1.44 | 21.25 | 0.20 | 0.29 | 813.56 | 1439.32 | 6475.94 | 7915.89 | B | True |
| warm_retrieval_uncached_question | 0 | 1 | 6 | A | 1177 | 4 | 6 | 1257.25 | 435.87 | 0.00 | 4.06 | 4.07 | 0.00 | 1704.30 | 91564.67 | 93272.18 | D | True |
| warm_retrieval_uncached_question | 0 | 1 | 6 | B | 1177 | 1 | 1 | 283.25 | 108.39 | 0.00 | 1.06 | 1.21 | 0.00 | 394.68 | 13806.01 | 14201.20 | D | True |
| warm_retrieval_uncached_question | 0 | 1 | 6 | C | 938 | 1 | 1 | 241.01 | 89.86 | 0.00 | 0.94 | 1.09 | 0.00 | 333.54 | 13623.18 | 13957.30 | D | True |
| warm_retrieval_uncached_question | 0 | 1 | 6 | D | 1177 | 1 | 1 | 633.49 | 2.39 | 19.90 | 0.44 | 0.33 | 814.97 | 1459.26 | 15584.60 | 17044.82 | D | True |
| warm_retrieval_uncached_question | 0 | 1 | 7 | A | 1309 | 4 | 6 | 1124.88 | 503.74 | 0.00 | 4.58 | 4.63 | 0.00 | 1641.08 | 103767.02 | 105411.29 | C | True |
| warm_retrieval_uncached_question | 0 | 1 | 7 | B | 1309 | 1 | 1 | 286.09 | 207.16 | 0.00 | 0.94 | 1.20 | 0.00 | 496.12 | 6567.29 | 7064.00 | C | True |
| warm_retrieval_uncached_question | 0 | 1 | 7 | C | 1042 | 1 | 1 | 377.21 | 98.52 | 0.00 | 0.99 | 1.16 | 0.00 | 478.59 | 10607.49 | 11086.60 | C | True |
| warm_retrieval_uncached_question | 0 | 1 | 7 | D | 1309 | 1 | 1 | 666.76 | 4.30 | 19.95 | 0.21 | 0.33 | 2410.91 | 3086.51 | 32974.34 | 36061.57 | D | False |
| warm_retrieval_uncached_question | 0 | 1 | 8 | A | 1518 | 4 | 6 | 1328.07 | 611.45 | 0.00 | 5.45 | 5.59 | 0.00 | 1958.20 | 216092.67 | 218054.26 | A | False |
| warm_retrieval_uncached_question | 0 | 1 | 8 | B | 1518 | 1 | 1 | 235.13 | 147.14 | 0.00 | 1.26 | 1.72 | 0.00 | 386.08 | 13706.66 | 14093.30 | C | False |
| warm_retrieval_uncached_question | 0 | 1 | 8 | C | 1213 | 1 | 1 | 223.82 | 111.19 | 0.00 | 0.98 | 1.31 | 0.00 | 338.02 | 7685.58 | 8024.11 | C | False |
| warm_retrieval_uncached_question | 0 | 1 | 8 | D | 1518 | 1 | 1 | 731.66 | 4.58 | 17.52 | 0.18 | 0.22 | 824.13 | 1565.69 | 6739.61 | 8305.96 | C | False |
| warm_retrieval_uncached_question | 0 | 1 | 9 | A | 1552 | 4 | 6 | 1199.51 | 624.60 | 0.00 | 5.65 | 5.92 | 0.00 | 1839.36 | 120846.38 | 122689.02 | B | False |
| warm_retrieval_uncached_question | 0 | 1 | 9 | B | 1552 | 1 | 1 | 284.12 | 172.26 | 0.00 | 1.36 | 1.74 | 0.00 | 460.34 | 9672.96 | 10133.90 | A | False |
| warm_retrieval_uncached_question | 0 | 1 | 9 | C | 1241 | 1 | 1 | 258.99 | 110.79 | 0.00 | 1.09 | 1.35 | 0.00 | 372.97 | 14787.23 | 15160.80 | B | False |
| warm_retrieval_uncached_question | 0 | 1 | 9 | D | 1552 | 1 | 1 | 672.70 | 4.39 | 19.27 | 0.20 | 0.29 | 878.11 | 1564.03 | 22179.83 | 23744.47 | A | False |
| warm_retrieval_uncached_question | 0 | 1 | 10 | A | 1713 | 4 | 6 | 1708.43 | 712.98 | 0.00 | 6.43 | 7.02 | 0.00 | 2438.98 | 111517.98 | 113960.28 | A | True |
| warm_retrieval_uncached_question | 0 | 1 | 10 | B | 1713 | 1 | 1 | 400.06 | 183.37 | 0.00 | 1.48 | 1.66 | 0.00 | 587.55 | 13780.00 | 14368.13 | A | True |
| warm_retrieval_uncached_question | 0 | 1 | 10 | C | 1370 | 1 | 1 | 309.22 | 117.08 | 0.00 | 1.24 | 1.43 | 0.00 | 429.76 | 6699.51 | 7129.78 | A | True |
| warm_retrieval_uncached_question | 0 | 1 | 10 | D | 1713 | 1 | 1 | 621.92 | 5.79 | 25.05 | 0.23 | 0.31 | 818.60 | 1452.07 | 16398.91 | 17851.64 | C | False |

## Per-method aggregates

```json
{
  "A": {
    "correct": 4,
    "questions": 10,
    "mean_retrieval_ms": 1883.2454225987021,
    "median_retrieval_ms": 1837.820285003545,
    "p95_retrieval_ms": 2438.9755399897695,
    "mean_end_to_end_ms": 103480.41624380057,
    "median_end_to_end_ms": 99341.73088600073,
    "mean_embedding_ms": 1412.7223079973191,
    "mean_gemini_ms_per_question": 101593.97498529725,
    "mean_gemini_ms_per_call": 16932.329164216208,
    "mean_gemini_calls": 6,
    "mean_retrieval_queries": 4
  },
  "B": {
    "correct": 4,
    "questions": 10,
    "mean_retrieval_ms": 443.0503902985947,
    "median_retrieval_ms": 427.5119999983872,
    "p95_retrieval_ms": 658.6140069994144,
    "mean_end_to_end_ms": 36462.229725099314,
    "median_end_to_end_ms": 14284.66276149993,
    "mean_embedding_ms": 323.8454603990249,
    "mean_gemini_ms_per_question": 36018.610326000635,
    "mean_gemini_ms_per_call": 36018.610326000635,
    "mean_gemini_calls": 1,
    "mean_retrieval_queries": 1
  },
  "C": {
    "correct": 6,
    "questions": 10,
    "mean_retrieval_ms": 383.2866341988847,
    "median_retrieval_ms": 355.49425950011937,
    "p95_retrieval_ms": 552.0784039981663,
    "mean_end_to_end_ms": 17220.81883609935,
    "median_end_to_end_ms": 13614.109479003673,
    "mean_embedding_ms": 302.26393330085557,
    "mean_gemini_ms_per_question": 16836.94433750061,
    "mean_gemini_ms_per_call": 16836.94433750061,
    "mean_gemini_calls": 1,
    "mean_retrieval_queries": 1
  },
  "D": {
    "correct": 3,
    "questions": 10,
    "mean_retrieval_ms": 1667.107173900149,
    "median_retrieval_ms": 1535.6091755020316,
    "p95_retrieval_ms": 3086.5072579981643,
    "mean_end_to_end_ms": 19700.207031598984,
    "median_end_to_end_ms": 18335.571765997884,
    "mean_embedding_ms": 662.2708030015929,
    "mean_gemini_ms_per_question": 18032.38190369957,
    "mean_gemini_ms_per_call": 18032.38190369957,
    "mean_gemini_calls": 1,
    "mean_retrieval_queries": 1
  }
}
```
