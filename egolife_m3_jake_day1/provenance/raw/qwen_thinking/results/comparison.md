# Jake DAY1 — Qwen first ten questions

Reasoning: `Qwen/Qwen3.5-4B` locally on CUDA at 2 FPS. Visual sampling is unchanged; user-authorized concurrent GPU execution with Gemini can affect both latency conditions. A/B/C use M3 native OpenRouter text-embedding-3-large; D independently embeds exported text with 302.ai Qwen3-Embedding-0.6B (1024D), local original SPLADE and BM25, then Qwen3-Reranker-0.6B.

All QA rows measure warm local retrieval with an uncached question. Snapshot loading, offline adaptation/compression, and fixed neutral-probe warmup are excluded and recorded in retrieval_warmup.jsonl. Actual query embeddings, searches and reranking remain timed; cloud-provider internal model state is not controlled. Mandol backend times include nested embeddings and unit lookup; parallel/nested timings are not additive. Retrieval total is measured wall time. TTFT is unavailable for the non-streaming API. Compression and adaptor use zero reasoning calls.

| Thinking enabled | GPU execution | Latency mode | Skipped segments | ASR degraded segments | Q | Method | Memory nodes | Retrieval queries | Qwen calls | Embed ms | Dense ms | Sparse ms | StreamMeCo/Mandol ms | Graph lookup ms | Rerank ms | Retrieval total ms | Qwen answer/controller ms | End-to-end ms | Answer | Correct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| False | concurrent with Gemini; contention possible | warm_retrieval_uncached_question | 1 | 0 | 1 | A | 296 | 4 | 6 | 1611.14 | 126.88 | 0.00 | 0.79 | 0.87 | 0.00 | 1741.30 | 55738.94 | 57482.91 |  | False |
| False | concurrent with Gemini; contention possible | warm_retrieval_uncached_question | 1 | 0 | 1 | B | 296 | 1 | 1 | 240.00 | 41.66 | 0.00 | 0.21 | 0.44 | 0.00 | 282.73 | 296.96 | 580.35 | B | True |
| False | concurrent with Gemini; contention possible | warm_retrieval_uncached_question | 1 | 0 | 1 | C | 230 | 1 | 1 | 225.85 | 30.78 | 0.00 | 0.19 | 0.40 | 0.00 | 257.62 | 296.63 | 554.88 | C | False |
| False | concurrent with Gemini; contention possible | warm_retrieval_uncached_question | 1 | 0 | 1 | D | 296 | 1 | 1 | 695.99 | 8.88 | 15.17 | 0.31 | 0.72 | 1559.65 | 2273.49 | 3889.89 | 6164.39 | D | False |
| False | concurrent with Gemini; contention possible | warm_retrieval_uncached_question | 3 | 0 | 2 | A | 687 | 4 | 6 | 2150.03 | 275.15 | 0.00 | 2.27 | 1.94 | 0.00 | 2431.52 | 42616.52 | 45050.98 |  | False |
| False | concurrent with Gemini; contention possible | warm_retrieval_uncached_question | 3 | 0 | 2 | B | 687 | 1 | 1 | 259.89 | 89.50 | 0.00 | 0.59 | 0.72 | 0.00 | 351.23 | 253.34 | 604.99 | B | False |
| False | concurrent with Gemini; contention possible | warm_retrieval_uncached_question | 3 | 0 | 2 | C | 539 | 1 | 1 | 346.83 | 52.76 | 0.00 | 0.39 | 0.61 | 0.00 | 401.05 | 258.70 | 660.44 | B | False |
| False | concurrent with Gemini; contention possible | warm_retrieval_uncached_question | 3 | 0 | 2 | D | 687 | 1 | 1 | 667.04 | 2.83 | 17.39 | 0.39 | 1.20 | 1652.62 | 2330.03 | 990.58 | 3321.70 | B | False |
| False | concurrent with Gemini; contention possible | warm_retrieval_uncached_question | 3 | 0 | 3 | A | 695 | 4 | 6 | 1440.03 | 285.07 | 0.00 | 2.49 | 2.14 | 0.00 | 1732.08 | 49224.29 | 50959.36 | B | False |
| False | concurrent with Gemini; contention possible | warm_retrieval_uncached_question | 3 | 0 | 3 | B | 695 | 1 | 1 | 187.02 | 76.51 | 0.00 | 0.55 | 0.76 | 0.00 | 265.39 | 255.85 | 521.78 | D | True |
| False | concurrent with Gemini; contention possible | warm_retrieval_uncached_question | 3 | 0 | 3 | C | 546 | 1 | 1 | 304.26 | 81.80 | 0.00 | 0.51 | 0.64 | 0.00 | 387.68 | 258.91 | 647.38 | D | True |
| False | concurrent with Gemini; contention possible | warm_retrieval_uncached_question | 3 | 0 | 3 | D | 695 | 1 | 1 | 675.30 | 2.61 | 17.75 | 0.41 | 1.14 | 1631.84 | 2317.03 | 1013.76 | 3331.89 | B | False |
| False | concurrent with Gemini; contention possible | warm_retrieval_uncached_question | 3 | 0 | 4 | A | 921 | 4 | 6 | 1815.84 | 403.14 | 0.00 | 3.32 | 2.93 | 0.00 | 2227.96 | 44838.71 | 47070.00 | D | False |
| False | concurrent with Gemini; contention possible | warm_retrieval_uncached_question | 3 | 0 | 4 | B | 921 | 1 | 1 | 364.24 | 97.62 | 0.00 | 0.77 | 0.95 | 0.00 | 464.20 | 254.05 | 718.69 | C | True |
| False | concurrent with Gemini; contention possible | warm_retrieval_uncached_question | 3 | 0 | 4 | C | 721 | 1 | 1 | 263.99 | 80.72 | 0.00 | 0.63 | 0.83 | 0.00 | 346.71 | 258.29 | 605.57 | B | False |
| False | concurrent with Gemini; contention possible | warm_retrieval_uncached_question | 3 | 0 | 4 | D | 921 | 1 | 1 | 608.22 | 2.94 | 17.44 | 0.45 | 1.19 | 1691.98 | 2309.72 | 1016.67 | 3327.74 | B | False |
| False | concurrent with Gemini; contention possible | warm_retrieval_uncached_question | 3 | 1 | 5 | A | 1302 | 4 | 6 | 1396.63 | 515.85 | 0.00 | 4.55 | 4.32 | 0.00 | 1924.63 | 46963.88 | 48891.90 | A | False |
| False | concurrent with Gemini; contention possible | warm_retrieval_uncached_question | 3 | 1 | 5 | B | 1302 | 1 | 1 | 387.23 | 128.08 | 0.00 | 1.16 | 1.34 | 0.00 | 518.59 | 263.56 | 782.97 | D | False |
| False | concurrent with Gemini; contention possible | warm_retrieval_uncached_question | 3 | 1 | 5 | C | 1015 | 1 | 1 | 314.65 | 104.11 | 0.00 | 0.98 | 1.10 | 0.00 | 421.51 | 256.70 | 678.68 | D | False |
| False | concurrent with Gemini; contention possible | warm_retrieval_uncached_question | 3 | 1 | 5 | D | 1302 | 1 | 1 | 631.81 | 4.18 | 25.23 | 0.63 | 1.65 | 1577.02 | 2222.51 | 1045.33 | 3269.47 | D | False |
| False | concurrent with Gemini; contention possible | warm_retrieval_uncached_question | 3 | 1 | 6 | A | 1342 | 4 | 6 | 1156.31 | 527.72 | 0.00 | 5.47 | 4.66 | 0.00 | 1697.77 | 65363.53 | 67064.98 | C | False |
| False | concurrent with Gemini; contention possible | warm_retrieval_uncached_question | 3 | 1 | 6 | B | 1342 | 1 | 1 | 218.89 | 147.66 | 0.00 | 1.40 | 1.36 | 0.00 | 370.11 | 254.46 | 625.14 | B | False |
| False | concurrent with Gemini; contention possible | warm_retrieval_uncached_question | 3 | 1 | 6 | C | 1047 | 1 | 1 | 291.94 | 108.48 | 0.00 | 0.93 | 1.13 | 0.00 | 403.17 | 255.16 | 658.76 | B | False |
| False | concurrent with Gemini; contention possible | warm_retrieval_uncached_question | 3 | 1 | 6 | D | 1342 | 1 | 1 | 654.20 | 2.81 | 17.29 | 0.42 | 1.47 | 1637.50 | 2302.82 | 1032.10 | 3336.00 | B | False |
| False | concurrent with Gemini; contention possible | warm_retrieval_uncached_question | 3 | 1 | 7 | A | 1521 | 4 | 6 | 3608.79 | 632.75 | 0.00 | 6.23 | 5.27 | 0.00 | 4256.77 | 43140.01 | 47400.03 | D | False |
| False | concurrent with Gemini; contention possible | warm_retrieval_uncached_question | 3 | 1 | 7 | B | 1521 | 1 | 1 | 217.97 | 163.84 | 0.00 | 1.40 | 15.07 | 0.00 | 399.28 | 261.43 | 661.46 | C | True |
| False | concurrent with Gemini; contention possible | warm_retrieval_uncached_question | 3 | 1 | 7 | C | 1184 | 1 | 1 | 276.25 | 114.74 | 0.00 | 1.09 | 1.21 | 0.00 | 394.05 | 255.24 | 649.82 | C | True |
| False | concurrent with Gemini; contention possible | warm_retrieval_uncached_question | 3 | 1 | 7 | D | 1521 | 1 | 1 | 688.37 | 2.87 | 18.15 | 0.45 | 1.79 | 1617.04 | 2319.00 | 1023.21 | 3343.47 | C | True |
| False | concurrent with Gemini; contention possible | warm_retrieval_uncached_question | 3 | 2 | 8 | A | 1786 | 4 | 6 | 1793.01 | 719.35 | 0.00 | 6.04 | 7.00 | 0.00 | 2529.51 | 80258.65 | 82791.55 | A | False |
| False | concurrent with Gemini; contention possible | warm_retrieval_uncached_question | 3 | 2 | 8 | B | 1786 | 1 | 1 | 293.01 | 186.89 | 0.00 | 1.81 | 2.36 | 0.00 | 485.20 | 259.52 | 745.31 | D | True |
| False | concurrent with Gemini; contention possible | warm_retrieval_uncached_question | 3 | 2 | 8 | C | 1391 | 1 | 1 | 260.07 | 130.34 | 0.00 | 1.26 | 1.42 | 0.00 | 393.96 | 261.24 | 656.02 | D | True |
| False | concurrent with Gemini; contention possible | warm_retrieval_uncached_question | 3 | 2 | 8 | D | 1786 | 1 | 1 | 755.52 | 6.05 | 17.41 | 0.55 | 1.68 | 1660.59 | 2433.82 | 1030.21 | 3465.40 | A | False |
| False | concurrent with Gemini; contention possible | warm_retrieval_uncached_question | 3 | 2 | 9 | A | 1844 | 4 | 6 | 1423.90 | 733.78 | 0.00 | 7.84 | 18.13 | 0.00 | 2188.22 | 87352.68 | 89544.48 | A | False |
| False | concurrent with Gemini; contention possible | warm_retrieval_uncached_question | 3 | 2 | 9 | B | 1844 | 1 | 1 | 283.08 | 184.52 | 0.00 | 1.86 | 2.35 | 0.00 | 472.91 | 270.54 | 743.99 | B | False |
| False | concurrent with Gemini; contention possible | warm_retrieval_uncached_question | 3 | 2 | 9 | C | 1435 | 1 | 1 | 265.12 | 140.04 | 0.00 | 1.32 | 1.51 | 0.00 | 408.93 | 255.71 | 665.16 | B | False |
| False | concurrent with Gemini; contention possible | warm_retrieval_uncached_question | 3 | 2 | 9 | D | 1844 | 1 | 1 | 634.24 | 6.32 | 19.33 | 0.49 | 2.11 | 1632.44 | 2284.90 | 1029.61 | 3315.81 | B | False |
| False | concurrent with Gemini; contention possible | warm_retrieval_uncached_question | 3 | 2 | 10 | A | 2039 | 4 | 6 | 1361.00 | 829.23 | 0.00 | 9.13 | 8.25 | 0.00 | 2212.62 | 47143.35 | 49360.34 | B | False |
| False | concurrent with Gemini; contention possible | warm_retrieval_uncached_question | 3 | 2 | 10 | B | 2039 | 1 | 1 | 348.54 | 212.88 | 0.00 | 2.19 | 2.44 | 0.00 | 567.27 | 256.79 | 824.65 | B | False |
| False | concurrent with Gemini; contention possible | warm_retrieval_uncached_question | 3 | 2 | 10 | C | 1591 | 1 | 1 | 3607.62 | 153.57 | 0.00 | 1.44 | 1.72 | 0.00 | 3765.29 | 309.42 | 4075.18 | C | False |
| False | concurrent with Gemini; contention possible | warm_retrieval_uncached_question | 3 | 2 | 10 | D | 2039 | 1 | 1 | 644.98 | 5.83 | 24.49 | 0.81 | 2.34 | 1735.76 | 2408.32 | 1038.92 | 3448.85 | B | False |

## Per-method aggregates

```json
{
  "A": {
    "correct": 0,
    "questions": 10,
    "mean_retrieval_ms": 2294.2381811968517,
    "median_retrieval_ms": 2200.4204989934806,
    "p95_retrieval_ms": 4256.770168998628,
    "mean_end_to_end_ms": 58561.65315889957,
    "median_end_to_end_ms": 50159.85313850251,
    "mean_embedding_ms": 1775.6675719021587,
    "mean_qwen_ms_per_question": 56264.05682290788,
    "mean_qwen_ms_per_call": 9377.342803817979,
    "mean_qwen_calls": 6,
    "mean_retrieval_queries": 4
  },
  "B": {
    "correct": 5,
    "questions": 10,
    "mean_retrieval_ms": 417.69089859735686,
    "median_retrieval_ms": 431.7409104987746,
    "p95_retrieval_ms": 567.27486399177,
    "mean_end_to_end_ms": 680.9309737014701,
    "median_end_to_end_ms": 690.0733510046848,
    "mean_embedding_ms": 279.98884889821056,
    "mean_qwen_ms_per_question": 262.64855850022286,
    "mean_qwen_ms_per_call": 262.64855850022286,
    "mean_qwen_calls": 1,
    "mean_retrieval_queries": 1
  },
  "C": {
    "correct": 3,
    "questions": 10,
    "mean_retrieval_ms": 717.9979126987746,
    "median_retrieval_ms": 397.54818999790587,
    "p95_retrieval_ms": 3765.290343988454,
    "mean_end_to_end_ms": 985.186059300031,
    "median_end_to_end_ms": 657.3877799964976,
    "mean_embedding_ms": 615.657331100374,
    "mean_qwen_ms_per_question": 266.6000672004884,
    "mean_qwen_ms_per_call": 266.6000672004884,
    "mean_qwen_calls": 1,
    "mean_retrieval_queries": 1
  },
  "D": {
    "correct": 1,
    "questions": 10,
    "mean_retrieval_ms": 2320.163444998616,
    "median_retrieval_ms": 2313.373014498211,
    "p95_retrieval_ms": 2433.8199449994136,
    "mean_end_to_end_ms": 3632.4709887980134,
    "median_end_to_end_ms": 3333.941775999847,
    "mean_embedding_ms": 665.5672232009238,
    "mean_qwen_ms_per_question": 1311.0304175992496,
    "mean_qwen_ms_per_call": 1311.0304175992496,
    "mean_qwen_calls": 1,
    "mean_retrieval_queries": 1
  }
}
```
