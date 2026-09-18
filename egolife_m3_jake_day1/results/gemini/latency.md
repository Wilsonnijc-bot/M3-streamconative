# Gemini — first ten questions — latency

Updated: 2026-09-15T16:00:47+00:00. **Complete: 40 verified QA predictions**.

**Method D:** up to **100 candidates → 20 final evidence nodes**, Qwen embedding and reranking via **302.ai**. These are the later rerun measurements; A/B/C retain their original measurements. The earlier two-node D result is retained only in provenance.

## Analysis — where the time goes

**The main costs are model/API calls, not graph bookkeeping.** Mandol’s two cloud stages dominate its warm retrieval; StreamMeCo’s one-shot retrieval is mostly embedding plus local similarity search; Gemini generation dominates memory construction.

This analysis uses the **10 completed questions per method** and **144 committed segments**. Retrieval values below are milliseconds; the overview explicitly uses seconds. `N` is the number of available, non-null stage observations. Missing measurements are not replaced by zero.

**Measurement boundary:** all QA engines were warmed with an unrelated probe; the actual question and its embeddings were uncached. Offline adaptation, snapshot loading and warmup are excluded. The original evaluation shared GPU resources with Qwen. Selected D rerun measurements, when present, come from a later execution period. These are potentially contended observations, not isolated-load measurements.

### 1. Overall picture

| Method | Correct | Retrievals / Q | Gemini calls / Q | Mean retrieval s | Median retrieval s | Mean total QA s | Median total QA s |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A · controller | 4/10 | 4.00 | 6.00 | 1.88 | 1.84 | 103.48 | 99.34 |
| B · one-shot | 4/10 | 1.00 | 1.00 | 0.4431 | 0.4275 | 36.46 | 14.28 |
| C · compressed one-shot | 6/10 | 1.00 | 1.00 | 0.3833 | 0.3555 | 17.22 | 13.61 |
| D · Mandol one-shot | 4/10 | 1.00 | 1.00 | 2.40 | 2.38 | 18.65 | 17.25 |

- **Mandol vs B:** mean warm retrieval is 5.42× longer. This is predominantly the extra reranker call and the different embedding service, not slow local vector search.
- **Compression:** C saves 59.76 ms in mean retrieval versus B (13.5%). Its mean local vector-search time is 32.5% lower. The embedding medians are almost identical, so do not credit compression for differences in cloud embedding response time.
- **Controller:** A used four retrieval rounds and six Gemini calls on every question in this run, reaching the forced-final-answer cap on **10/10 questions**. It obtained the same 4/10 accuracy as B while taking much longer. This is evidence about these ten questions, not a general accuracy ranking.
- **Total QA is not retrieval latency:** B’s Q5 took 154.74 seconds end to end, largely in answer generation. B/C median total QA is much closer than their means. The observed reduction in retrieval time is only about 60 ms; it cannot explain the much larger difference in mean answer latency.

### 2. Warm Mandol: each stage

**Mean 2,399.98 ms; median 2,375.08 ms.** Dense embedding and reranking together account for approximately **99.2%** of mean wall time. Their calls occur sequentially: embedding during hybrid retrieval, then reranking after candidates are collected.

| Stage · N=10 | Mean ms | Median ms | Scope |
| --- | --- | --- | --- |
| Question / candidate-scope preparation | 1.90 | 1.89 | Local; before hybrid search |
| Dense text → vector API | 743.56 | 714.68 | 302.ai Qwen3-Embedding-0.6B, 1024D; network + provider time |
| Dense vector similarity search | 6.40 | 6.21 | Local; excludes the embedding API; includes nested lookups |
| SPLADE query-vector calculation | 10.85 | 10.80 | Local sparse encoder; INCLUDED in the SPLADE backend below |
| SPLADE encoder + sparse search | 13.78 | 13.72 | Full backend; overlaps the dense branch |
| BM25 query token/preparation | 5.85 | 5.24 | Local lexical preparation; INCLUDED in BM25 below |
| BM25 preparation + lexical search | 7.12 | 6.35 | Full backend; overlaps other retrieval work |
| RRF fusion | 0.5137 | 0.5269 | Combine backend candidates |
| MemoryUnit lookup | 1.40 | 1.40 | Nested inside backend searches; do not add again |
| Candidate text / MemorySpace lookup | 3.78 | 3.61 | Prepare selected candidates and reranker inputs |
| Cloud reranking | 1,638.41 | 1,635.35 | 302.ai Qwen3-Reranker-0.6B; after hybrid search |
| Warm engine readiness check | 0.0173 | 0.0155 | Tiny check; no model/index reload |
| Hybrid-search wall subtotal | 755.57 | 727.17 | INCLUDES dense embedding, backends and fusion |
| TOTAL warm retrieval | 2,399.98 | 2,375.08 | Independently measured wall time |

**Do not add every row.** Query-vector computation is nested in its backend, MemoryUnit lookup is nested in search, and dense/sparse work overlaps. The hybrid subtotal is not an additional stage. The dense QueryBundle “compute time” is another wrapper around the same cloud embedding request—not a second dense embedding calculation.

The local dense search averages only **6.40 ms**. Its speed does not establish an apples-to-apples advantage over StreamMeCo: D uses a different embedding model, 1024 rather than 3072 dimensions, and a different search representation.

The reranker also explains the long tail: on Q10 it took **1,693.7 ms**, bringing total retrieval to **2,413.5 ms**. Mean and median reranker timings are listed above. Ten samples are too few to infer a stable production tail. No initialization time needs to be subtracted from these totals—it was already excluded.

### 3. B/C one-shot: embedding versus similarity calculation

**Text embedding** means generating a vector from the query. **Vector similarity/search** means comparing that vector with stored memory vectors. They are different stages. “Embedding calculation” is not a third stage unless referring specifically to a separate encoder such as Mandol’s SPLADE.

| Stage · N=10 per method | B mean ms | B median ms | C mean ms | C median ms |
| --- | --- | --- | --- | --- |
| Construct literal question query | 0.0008 | 0.0005 | 0.0006 | 0.0005 |
| Prepare/back-translate query | 0.0127 | 0.0117 | 0.0116 | 0.0117 |
| Text → vector stage, including client overhead | 323.85 | 283.68 | 302.26 | 283.97 |
| Compare/search existing memory vectors | 116.45 | 111.33 | 78.59 | 84.45 |
| StreamMeCo/TMR scoring | 0.9191 | 0.9818 | 0.7766 | 0.8859 |
| Graph/node selection | 1.15 | 1.21 | 1.00 | 1.09 |
| Reranking — not used | 0.00 | 0.00 | 0.00 | 0.00 |
| Sparse search — not used | 0.00 | 0.00 | 0.00 | 0.00 |
| TOTAL one-shot retrieval | 443.05 | 427.51 | 383.29 | 355.49 |

The OpenRouter API-call-only means are **323.08 ms (B)** and **301.46 ms (C)**; the slightly larger embedding-stage values above include local orchestration. These are API wall times, not isolated provider GPU inference times. The provider’s queue, network and model compute cannot be separated from these records.

Embedding occupies about **73.1% of B** and **78.9% of C** retrieval time. Local similarity search contributes most of the rest; scoring and graph selection are about a millisecond each. B/C use neither a sparse encoder nor a reranker.

### 4. Memory construction: mean and median for every recorded stage

**Optimized measurements only:** segments **27–144 (118 segments)**, after concurrent ASR, pooled HTTP, per-clip embedding batches and lookahead were enabled. Earlier-protocol segments 1–26 are excluded from this table. Clips have different durations, and outages, cache reuse and shared-GPU work occurred.

Means and medians are calculated independently for each row; medians of serial stages are not additive either. Times below are milliseconds. Null observations are omitted and counted in N; they are not assigned zero. ASR spans include any retries or cache lookup actually performed for the committed clip. Cached voice/face preprocessing can make a stage unavailable. These are observed stage spans, not estimates of uncached service cost.

| Stage | Optimized N | Optimized mean ms | Optimized median ms |
| --- | --- | --- | --- |
| Clip decoding | 118 | 4,790.50 | 4,685.02 |
| Deepgram ASR span | 117 | 997.01 | 884.27 |
| MAI ASR span | 117 | 4,278.92 | 1,053.92 |
| ASR stage wall time | 117 | 4,500.52 | 1,104.93 |
| Audio segmentation | 117 | 7.98 | 7.23 |
| Speaker embedding · CAM++ | 113 | 1,211.07 | 1,198.55 |
| Face detection/recognition | 117 | 3,777.68 | 3,907.72 |
| Face clustering | 117 | 14.27 | 7.24 |
| VLM input/context preparation | 118 | 3,906.14 | 4,055.05 |
| Gemini memory-generation API | 118 | 54,888.64 | 43,780.16 |
| Memory-text embedding · batch after clip 26 | 118 | 573.70 | 526.95 |
| Graph updates · voice/face/text combined | 118 | 570.29 | 411.24 |

**Gemini is the main construction bottleneck:** optimized memory generation averages **54.89 s** (median **43.78 s**), approximately **84.4%** of the mean ordered processing span. Mean graph-update time is only **0.57 s**.

**Means expose outages; medians show the typical case.** Optimized MAI spans have a 1.05-second median but a 4.28-second mean. Segments 65, 67 and 98 each spent roughly 122–125 seconds in MAI, including failed attempts/retries. Gemini itself also had long calls, including about 248 seconds on segment 84.

**The embedding optimization is visible, but not a controlled causal estimate:** earlier memory-text embedding averaged 2.15 seconds; optimized per-clip batches averaged 0.574 seconds. Clip contents, batch sizes, connection reuse and service conditions also differ, so do not attribute the entire difference to batching alone.

### 5. Why a prefetched clip can show ~200 seconds without taking ~200 seconds of model work

| Optimized pipeline span | N | Mean seconds | Median seconds |
| --- | --- | --- | --- |
| Preparation worker: trimming, decode and ASR | 118 | 11.03 | 7.79 |
| Consumer waiting for preparation | 118 | 1.48 | 0.000012 |
| Prepared clip waiting for chronological turn | 118 | 121.92 | 110.38 |
| Ordered processing through graph/audit work | 118 | 65.02 | 54.80 |
| Ordered processing through persisted checkpoint | 118 | 66.94 | 57.20 |
| Full admission → persisted checkpoint | 118 | 199.89 | 183.37 |

A future clip is admitted while earlier clips are still being processed. Its queue wait therefore counts toward admission-to-checkpoint latency. That is real latency, but it is not extra model inference and does not mean the pipeline completes only one clip every 200 seconds.

The median consumer wait is effectively zero: lookahead usually had the next clip ready. The roughly 122-second average ready-queue wait reflects the ordered Gemini stage being the bottleneck. Increasing lookahead further is unlikely to help much when preparation is already hidden; it can increase waiting and memory use.

**Deployment implication:** if new clips arrive every 30 seconds, the observed roughly 67-second mean ordered stage through checkpoint would not keep up with that arrival rate on one sequential memory worker. Lookahead hides preparation, but cannot remove the sustained Gemini bottleneck. This is a conditional inference from this run, not a separate live-stream benchmark; admission-to-checkpoint timing also does not measure any backlog before a clip is admitted.

Preparation overlaps work on other clips, so do not add it again to a segment’s queue/ordered total. The legacy `end_to_end_memory_generation_ms` field changed timing boundaries after optimization; a pooled mean of that field across all 144 clips would be misleading. The checkpoint event spans above are the consistent optimized end-to-end measurements. Pauses and restarts must be considered separately when estimating total experiment completion time.

**Reading the results:** C had the best observed score (6/10) and lowest mean retrieval time here, but ten questions and shared-GPU execution are insufficient for a general ranking. The actionable performance targets are Gemini generation for construction, embedding service latency for B/C, and embedding plus reranking service latency for D.

---

## Detailed measurements

All values below are measured milliseconds unless stated otherwise. Empty fields mean unavailable, not zero. Overlapping stages must not be added as end-to-end latency. Cached acquisition, warmup, retries and execution-policy changes remain separate.

**Measurement context:** The Qwen thinking identity-v2 full benchmark was active on the same Hyperstack VM/GPU during Gemini QA evaluation. Warm-engine timings are actual observations under potentially contended GPU load, not an isolated-GPU benchmark. The amount of interference was not measured.

## Memory construction

| Segment | Nodes | Decode | ASR stage | Reasoning | Text embedding | Ready queue | Ordered processing | Admission → checkpoint |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 12 | 3,001.43 | 19,458.14 | 67,238.82 | 5,905.30 | — | — | — |
| 2 | 21 | 3,729.92 | 6,194.66 | 97,825.06 | 1,058.71 | — | — | — |
| 3 | 30 | 4,259.73 | 4,571.19 | 22,292.89 | 1,643.42 | — | — | — |
| 4 | 44 | 5,215.69 | 123,365.58 | 25,699.50 | 2,472.29 | — | — | — |
| 5 | 53 | 4,006.95 | 972.42 | 58,517.77 | 1,528.50 | — | — | — |
| 6 | 61 | 3,838.89 | 1,893.36 | 39,697.00 | 2,245.32 | — | — | — |
| 7 | 69 | 5,249.54 | 124,543.70 | 81,124.67 | 2,125.75 | — | — | — |
| 8 | 81 | 5,033.94 | 3,029.17 | 26,566.43 | 2,132.11 | — | — | — |
| 9 | 89 | 5,004.91 | — | 51,175.15 | 2,350.89 | — | — | — |
| 10 | 99 | 3,517.94 | 2,059.45 | 61,524.48 | 693.94 | — | — | — |
| 11 | 113 | 3,389.84 | 1,475.16 | 30,306.39 | 1,351.85 | — | — | — |
| 12 | 123 | 4,349.58 | 1,275.72 | 50,037.18 | 1,970.76 | — | — | — |
| 13 | 135 | 4,087.02 | 2,113.23 | 31,681.19 | 852.61 | — | — | — |
| 14 | 151 | 4,052.49 | 2,687.03 | 70,455.15 | 2,842.97 | — | — | — |
| 15 | 162 | 4,024.76 | 1,603.04 | 63,411.41 | 3,072.86 | — | — | — |
| 16 | 173 | 4,091.84 | 2,409.42 | 58,795.47 | 1,895.89 | — | — | — |
| 17 | 192 | 3,957.84 | 4,639.54 | 44,757.12 | 1,995.50 | — | — | — |
| 18 | 202 | 4,091.34 | 2,040.04 | 23,977.46 | 1,709.30 | — | — | — |
| 19 | 216 | 3,978.41 | 4,917.56 | 110,356.56 | 2,054.26 | — | — | — |
| 20 | 228 | 4,116.70 | 2,280.49 | 24,792.58 | 1,537.02 | — | — | — |
| 21 | 241 | 4,181.59 | 2,188.79 | 45,529.07 | 2,299.61 | — | — | — |
| 22 | 250 | 4,030.00 | 2,544.31 | 55,621.13 | 1,735.81 | — | — | — |
| 23 | 264 | 3,905.41 | 4,580.12 | 55,125.44 | 3,754.71 | — | — | — |
| 24 | 271 | 481.56 | 1,201.55 | 13,544.72 | 3,103.27 | — | — | — |
| 25 | 288 | 3,860.88 | 1,418.74 | 46,889.65 | 1,944.36 | — | — | — |
| 26 | 298 | 4,046.66 | 1,719.21 | 46,819.66 | 1,589.37 | — | — | — |
| 27 | 309 | 5,535.48 | — | 18,671.20 | 869.09 | 1.01 | 24,042.39 | 32,104.69 |
| 28 | 321 | 5,649.39 | 1,092.42 | 66,817.27 | 501.64 | 23,496.51 | 79,319.42 | 111,995.28 |
| 29 | 330 | 6,688.85 | 1,046.17 | 38,296.25 | 881.89 | 0.22 | 51,216.68 | 62,130.41 |
| 30 | 351 | 6,886.70 | 1,768.52 | 25,117.48 | 549.02 | 50,826.68 | 35,946.52 | 98,725.80 |
| 31 | 364 | 6,847.48 | 1,720.39 | 22,875.52 | 484.95 | 87,714.61 | 33,760.88 | 133,152.62 |
| 32 | 373 | 3,830.23 | 1,684.53 | 42,849.02 | 499.13 | 62,911.24 | 50,990.30 | 122,665.99 |
| 33 | 383 | 5,084.10 | 1,027.27 | 33,494.95 | 499.52 | 77,323.13 | 44,009.54 | 130,806.34 |
| 34 | 394 | 3,846.85 | 984.62 | 68,008.83 | 1,257.82 | 89,851.07 | 78,513.17 | 175,824.11 |
| 35 | 415 | 4,229.03 | 1,095.12 | 56,027.00 | 860.95 | 116,426.03 | 67,684.05 | 192,699.18 |
| 36 | 429 | 4,037.07 | 932.47 | 73,919.89 | 477.26 | 140,806.17 | 83,629.10 | 232,362.69 |
| 37 | 441 | 4,791.75 | 1,052.39 | 34,242.10 | 512.39 | 144,297.46 | 44,278.13 | 198,047.57 |
| 38 | 453 | 3,559.96 | 899.90 | 64,928.42 | 705.47 | 122,994.78 | 74,502.38 | 204,811.64 |
| 39 | 465 | 4,043.18 | 1,563.68 | 31,438.72 | 363.71 | 112,276.94 | 41,538.79 | 162,881.78 |
| 40 | 476 | 3,845.64 | 1,131.41 | 57,300.47 | 642.90 | 110,862.09 | 67,418.05 | 186,079.17 |
| 41 | 489 | 3,907.67 | 3,357.84 | 56,266.69 | 615.86 | 101,121.31 | 65,839.64 | 177,478.82 |
| 42 | 498 | 3,948.47 | 1,163.23 | 72,210.31 | 582.14 | 127,685.90 | 82,147.48 | 218,111.05 |
| 43 | 508 | 4,098.97 | 1,096.05 | 47,945.04 | 562.38 | 142,442.96 | 57,753.36 | 208,559.06 |
| 44 | 520 | 3,763.93 | 960.13 | 80,052.45 | 661.16 | 135,364.67 | 89,599.79 | 232,407.73 |
| 45 | 534 | 3,884.91 | 842.91 | 28,684.02 | 479.40 | 142,897.90 | 37,918.90 | 188,300.14 |
| 46 | 543 | 4,023.42 | 937.25 | 19,743.95 | 372.40 | 122,618.51 | 29,393.34 | 159,992.31 |
| 47 | 555 | 4,225.32 | 1,204.99 | 36,856.98 | 378.62 | 62,341.49 | 47,468.19 | 117,934.18 |
| 48 | 564 | 4,102.13 | 926.38 | 74,995.45 | 439.46 | 71,704.77 | 84,187.47 | 164,210.37 |
| 49 | 572 | 4,207.58 | 1,421.14 | 20,945.81 | 441.51 | 125,566.56 | 30,658.99 | 165,522.83 |
| 50 | 581 | 3,888.86 | 1,440.42 | 49,494.26 | 521.45 | 109,894.11 | 59,261.86 | 177,373.15 |
| 51 | 595 | 4,068.73 | 3,280.22 | 52,918.52 | 420.91 | 82,427.21 | 62,410.64 | 155,644.76 |
| 52 | 606 | 3,751.15 | 885.72 | 22,780.21 | 384.56 | 117,557.99 | 31,796.36 | 156,826.13 |
| 53 | 614 | 2,711.44 | 854.10 | 43,924.19 | 515.85 | 92,278.64 | 50,041.86 | 148,633.90 |
| 54 | 622 | 1,801.16 | 1,132.84 | 41,011.85 | 399.39 | 82,189.57 | 44,498.27 | 131,633.14 |
| 55 | 634 | 4,067.79 | 910.06 | 32,904.67 | 490.05 | 90,847.65 | 41,933.71 | 140,979.12 |
| 56 | 642 | 3,426.24 | 1,848.37 | 34,533.50 | 409.74 | 82,270.10 | 41,697.26 | 131,808.82 |
| 57 | 655 | 4,033.74 | 1,013.80 | 36,684.77 | 465.86 | 79,451.27 | 45,964.00 | 133,443.40 |
| 58 | 667 | 3,514.36 | 871.16 | 28,062.86 | 541.35 | 84,018.23 | 37,731.07 | 129,245.04 |
| 59 | 677 | 3,746.41 | 2,257.70 | 22,315.23 | 522.31 | 78,487.21 | 33,316.78 | 120,968.22 |
| 60 | 687 | 3,916.24 | 1,136.58 | 59,974.99 | 1,676.70 | 66,687.89 | 71,116.77 | 146,359.71 |
| 61 | 699 | 4,341.90 | 1,042.69 | 63,825.36 | 521.06 | 99,668.67 | 73,886.41 | 182,577.92 |
| 62 | 711 | 4,104.95 | 1,138.04 | 35,909.45 | 538.00 | 141,258.83 | 45,697.80 | 195,049.76 |
| 63 | 718 | 4,159.73 | 1,108.34 | 38,101.31 | 393.01 | 115,118.08 | 47,288.79 | 171,461.60 |
| 64 | 732 | 4,174.98 | 1,580.37 | 32,993.34 | 449.04 | 88,925.97 | 43,700.45 | 141,711.69 |
| 65 | 742 | 4,120.61 | 123,526.30 | 62,812.99 | 1,547.38 | 0.13 | 73,176.15 | 203,612.61 |
| 66 | 755 | 4,678.00 | 1,021.08 | 100,882.63 | 555.80 | 147,291.33 | 113,248.65 | 269,370.08 |
| 67 | 776 | 4,327.37 | 124,881.60 | 181,682.28 | 624.21 | 93,047.12 | 191,441.79 | 416,921.17 |
| 68 | 791 | 5,934.44 | 6,306.93 | 42,961.01 | 421.85 | 293,711.76 | 52,554.99 | 361,762.93 |
| 69 | 798 | 4,446.16 | 1,649.73 | 55,678.53 | 592.92 | 239,295.43 | 64,491.76 | 313,081.99 |
| 70 | 808 | 2,221.74 | 1,081.18 | 14,699.58 | 416.70 | 116,097.77 | 17,651.27 | 139,267.55 |
| 71 | 818 | 3,104.38 | 747.26 | 28,381.33 | 552.76 | 81,333.00 | 35,192.69 | 123,364.18 |
| 72 | 825 | 4,355.31 | 1,403.28 | 24,555.67 | 465.56 | 49,610.69 | 33,125.53 | 92,221.17 |
| 73 | 840 | 4,488.01 | 6,282.92 | 34,740.71 | 565.22 | 59,492.57 | 43,785.71 | 117,410.58 |
| 74 | 852 | 4,893.33 | 1,830.74 | 43,250.22 | 575.24 | 72,184.83 | 53,341.19 | 135,671.33 |
| 75 | 863 | 5,052.97 | 969.63 | 67,559.59 | 532.61 | 93,014.81 | 78,396.06 | 180,916.84 |
| 76 | 879 | 4,250.90 | 1,234.26 | 34,722.00 | 411.82 | 127,926.32 | 47,081.62 | 184,110.09 |
| 77 | 887 | 4,995.54 | 1,047.98 | 44,386.26 | 513.92 | 121,452.63 | 54,700.73 | 185,738.02 |
| 78 | 899 | 5,478.38 | 1,059.59 | 120,076.09 | 653.63 | 97,470.13 | 129,849.37 | 237,145.44 |
| 79 | 911 | 4,769.49 | 1,068.32 | 81,075.61 | 585.92 | 180,835.50 | 90,943.83 | 281,219.91 |
| 80 | 924 | 4,484.32 | 1,189.84 | 52,814.57 | 384.97 | 217,240.01 | 63,626.96 | 289,905.96 |
| 81 | 938 | 4,158.07 | 1,170.23 | 198,975.47 | 646.31 | 151,383.28 | 210,933.71 | 371,094.84 |
| 82 | 948 | 4,908.45 | 831.35 | 58,986.48 | 617.48 | 271,104.41 | 68,474.48 | 348,685.65 |
| 83 | 964 | 5,265.79 | 1,045.72 | 37,999.93 | 409.63 | 275,334.82 | 50,916.36 | 336,328.17 |
| 84 | 979 | 4,786.10 | 1,192.72 | 247,565.49 | 746.74 | 116,022.31 | 258,075.51 | 383,592.40 |
| 85 | 993 | 6,012.79 | 1,004.13 | 40,333.14 | 566.01 | 304,570.97 | 50,977.09 | 366,243.11 |
| 86 | 1002 | 4,277.12 | 1,040.67 | 25,147.94 | 418.91 | 305,671.29 | 35,811.12 | 351,019.89 |
| 87 | 1014 | 4,821.51 | 1,419.93 | 142,063.19 | 525.54 | 82,466.44 | 153,052.89 | 245,994.59 |
| 88 | 1029 | 4,764.85 | 937.33 | 40,709.66 | 460.45 | 185,583.10 | 51,559.08 | 246,449.75 |
| 89 | 1038 | 4,788.18 | 1,061.83 | 64,380.32 | 509.06 | 201,080.96 | 73,961.12 | 284,561.93 |
| 90 | 1049 | 4,611.58 | 1,769.08 | 212,618.85 | 868.59 | 121,501.06 | 223,252.18 | 354,738.50 |
| 91 | 1059 | 4,410.77 | 988.23 | 48,819.91 | 449.52 | 294,259.14 | 58,190.79 | 361,455.31 |
| 92 | 1070 | 4,932.34 | 992.02 | 43,846.27 | 340.18 | 277,925.75 | 54,491.84 | 342,051.53 |
| 93 | 1082 | 4,281.63 | 1,772.94 | 108,081.96 | 580.05 | 109,148.24 | 119,788.59 | 238,913.47 |
| 94 | 1098 | 4,523.34 | 1,810.10 | 109,926.49 | 459.31 | 169,999.73 | 120,824.94 | 301,647.52 |
| 95 | 1114 | 5,892.13 | 1,518.73 | 32,819.82 | 410.21 | 235,915.34 | 43,689.20 | 290,959.12 |
| 96 | 1125 | 5,006.39 | 1,120.70 | 49,696.92 | 580.39 | 161,058.48 | 59,375.71 | 230,030.19 |
| 97 | 1133 | 5,215.92 | 1,156.45 | 66,535.30 | 1,059.57 | 99,146.26 | 76,789.76 | 186,119.12 |
| 98 | 1139 | 283.03 | 121,702.05 | 10,566.98 | 656.28 | 0.11 | 13,172.19 | 137,190.57 |
| 99 | 1155 | 4,478.86 | 3.30 | 36,113.18 | 655.42 | 132,736.27 | 46,635.58 | 187,667.69 |
| 100 | 1169 | 4,679.50 | 1,165.77 | 47,969.25 | 477.43 | 179,978.69 | 59,293.15 | 249,142.35 |
| 101 | 1177 | 2,167.99 | 1,380.22 | 29,326.42 | 570.09 | 105,875.30 | 31,832.56 | 144,163.89 |
| 102 | 1184 | 5,087.82 | 6,180.33 | 64,745.17 | 486.27 | 84,894.55 | 73,291.10 | 173,095.69 |
| 103 | 1195 | 3,954.05 | 1,093.83 | 105,782.22 | 506.15 | 104,893.26 | 116,015.31 | 229,932.38 |
| 104 | 1206 | 4,947.62 | 1,027.71 | 45,319.83 | 767.13 | 186,397.24 | 55,714.80 | 252,180.22 |
| 105 | 1223 | 4,988.50 | 2,104.25 | 51,691.35 | 685.65 | 167,947.13 | 63,420.67 | 242,488.72 |
| 106 | 1242 | 4,827.07 | 1,758.81 | 43,062.55 | 581.23 | 116,077.40 | 56,047.50 | 182,636.14 |
| 107 | 1256 | 5,874.44 | 1,827.30 | 49,448.12 | 616.91 | 115,362.41 | 61,524.84 | 188,327.89 |
| 108 | 1266 | 6,528.63 | 3,168.52 | 119,738.98 | 542.26 | 111,167.51 | 130,801.35 | 255,699.85 |
| 109 | 1278 | 6,318.06 | 1,021.91 | 41,318.08 | 449.04 | 188,433.41 | 54,437.99 | 254,558.63 |
| 110 | 1290 | 5,677.37 | 1,693.33 | 43,714.04 | 550.86 | 181,798.62 | 54,904.25 | 247,887.87 |
| 111 | 1300 | 5,792.30 | 951.12 | 52,933.67 | 421.18 | 105,840.97 | 63,871.28 | 180,789.98 |
| 112 | 1309 | 2,245.26 | 788.88 | 10,929.74 | 435.02 | 119,756.29 | 12,755.29 | 139,076.78 |
| 113 | 1317 | 4,545.38 | 975.55 | 53,759.47 | 539.89 | 76,765.24 | 62,038.88 | 148,314.60 |
| 114 | 1334 | 4,690.54 | 1,226.37 | 37,287.94 | 571.77 | 74,457.46 | 47,834.21 | 132,564.63 |
| 115 | 1346 | 4,605.31 | 1,055.28 | 27,052.90 | 590.38 | 107,889.87 | 37,794.27 | 155,556.15 |
| 116 | 1357 | 5,332.25 | 872.15 | 64,716.01 | 611.18 | 82,954.32 | 74,883.00 | 168,611.56 |
| 117 | 1369 | 5,575.15 | 1,203.90 | 31,440.03 | 591.59 | 109,559.34 | 43,276.57 | 164,096.28 |
| 118 | 1381 | 5,210.50 | 1,155.52 | 24,630.88 | 541.17 | 115,464.82 | 34,604.21 | 160,978.59 |
| 119 | 1395 | 6,087.55 | 1,004.17 | 90,227.78 | 471.78 | 74,519.66 | 100,941.82 | 187,120.44 |
| 120 | 1409 | 4,890.15 | 1,157.40 | 35,167.10 | 509.48 | 133,286.02 | 46,115.01 | 190,289.84 |
| 121 | 1420 | 5,477.03 | 1,004.24 | 37,674.27 | 476.00 | 144,712.63 | 48,134.03 | 203,959.18 |
| 122 | 1430 | 6,088.76 | 1,049.07 | 59,377.64 | 465.41 | 91,553.57 | 69,510.61 | 172,635.57 |
| 123 | 1447 | 5,353.59 | 917.26 | 32,011.75 | 491.03 | 115,508.13 | 42,414.46 | 168,822.02 |
| 124 | 1464 | 5,364.22 | 1,016.46 | 42,040.40 | 493.44 | 109,327.26 | 55,246.11 | 175,929.89 |
| 125 | 1477 | 6,130.92 | 1,065.19 | 32,433.76 | 483.78 | 94,633.14 | 46,028.32 | 152,369.25 |
| 126 | 1488 | 7,101.02 | 983.50 | 110,367.04 | 549.34 | 97,018.91 | 122,185.95 | 231,948.89 |
| 127 | 1510 | 7,322.68 | 1,268.23 | 26,596.27 | 661.17 | 163,526.78 | 40,787.87 | 217,701.08 |
| 128 | 1518 | 4,456.00 | 1,126.22 | 29,961.49 | 755.65 | 162,259.75 | 35,561.61 | 207,815.36 |
| 129 | 1525 | 4,562.26 | 1,399.56 | 39,362.92 | 1,320.33 | 78,127.51 | 47,645.89 | 135,935.52 |
| 130 | 1537 | 5,762.17 | 1,130.35 | 139,272.45 | 564.07 | 83,543.97 | 154,269.51 | 249,447.42 |
| 131 | 1546 | 5,642.92 | 1,102.97 | 25,570.30 | 420.83 | 199,660.99 | 35,477.93 | 246,843.16 |
| 132 | 1552 | 3,492.42 | 1,059.56 | 52,410.42 | 301.43 | 190,437.99 | 56,791.10 | 255,853.75 |
| 133 | 1563 | 4,272.38 | 1,120.36 | 19,828.14 | 518.68 | 94,236.28 | 27,353.25 | 131,290.71 |
| 134 | 1575 | 5,104.75 | 949.70 | 49,242.04 | 522.11 | 84,760.41 | 60,920.84 | 156,466.37 |
| 135 | 1590 | 5,547.41 | 962.63 | 46,146.96 | 579.86 | 86,281.29 | 59,726.67 | 157,119.01 |
| 136 | 1603 | 5,777.20 | 1,022.81 | 21,137.61 | 501.59 | 118,339.40 | 32,016.87 | 162,062.31 |
| 137 | 1619 | 6,775.04 | 1,290.67 | 44,429.13 | 578.74 | 88,234.10 | 59,687.03 | 161,196.08 |
| 138 | 1629 | 5,555.85 | 2,211.65 | 27,105.96 | 620.09 | 89,003.44 | 41,785.39 | 143,473.55 |
| 139 | 1641 | 7,617.54 | 1,028.09 | 86,643.67 | 528.35 | 97,435.24 | 99,863.18 | 211,087.72 |
| 140 | 1654 | 8,453.45 | 1,047.54 | 44,193.08 | 950.63 | 136,807.53 | 56,743.42 | 208,046.35 |
| 141 | 1668 | 6,903.22 | 970.83 | 26,738.10 | 663.75 | 153,561.81 | 38,406.08 | 204,666.10 |
| 142 | 1681 | 6,531.60 | 1,104.93 | 31,388.88 | 353.48 | 92,419.94 | 42,627.49 | 147,596.99 |
| 143 | 1699 | 6,266.02 | 1,387.96 | 74,125.99 | 523.32 | 78,160.20 | 85,772.96 | 176,070.44 |
| 144 | 1713 | 5,929.98 | 1,281.86 | 75,950.93 | 608.44 | 125,691.80 | 86,909.30 | 224,140.83 |

The two latency columns on the right are unavailable for older serial records. Their original `end_to_end_memory_generation_ms` values remain in the raw audit; they are not silently mixed with pipeline admission-to-checkpoint measurements.

## Preprocessing and graph-update detail

| Segment | Deepgram | MAI | Speech embedding | Face detection | Face clustering | Graph update | ASR cache/precompute |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 531.07 | 18,927.07 | 1,164.25 | 3,983.93 | 4.16 | 2.90 | False/False |
| 2 | 412.63 | 5,782.02 | 134.93 | 3,690.94 | 5.28 | 2.36 | False/False |
| 3 | 931.44 | 3,639.74 | 197.55 | 3,243.90 | 7.33 | 4.91 | False/False |
| 4 | 652.32 | 122,713.26 | 1,328.85 | 5,426.02 | 11.96 | 15.61 | False/False |
| 5 | 299.08 | 673.34 | — | 3,730.16 | 4.05 | 0.19 | False/False |
| 6 | 826.90 | 1,066.46 | 129.64 | 3,457.44 | 3.61 | 5.47 | False/False |
| 7 | 923.72 | 123,619.97 | 886.01 | 5,835.95 | 5.12 | 7.60 | False/False |
| 8 | 868.62 | 2,160.54 | 1,125.20 | 5,004.81 | 1.87 | 12.87 | False/False |
| 9 | — | — | — | — | — | 11.45 | True/False |
| 10 | 990.02 | 1,069.42 | 1,292.79 | 4,927.35 | 2.64 | 9.39 | False/False |
| 11 | 308.02 | 1,167.14 | 510.29 | 3,015.32 | 2.79 | 26.23 | False/False |
| 12 | 256.92 | 1,018.80 | 245.77 | 3,806.34 | 8.63 | 28.48 | False/False |
| 13 | 902.15 | 1,211.08 | 394.88 | 3,237.88 | 3.61 | 36.62 | False/False |
| 14 | 953.78 | 1,733.24 | 444.20 | 3,221.18 | 3.20 | 58.25 | False/False |
| 15 | 433.07 | 1,169.97 | 370.00 | 3,899.11 | 3.41 | 49.12 | False/False |
| 16 | 985.76 | 1,423.65 | 409.06 | 3,690.81 | 6.44 | 81.44 | False/False |
| 17 | 964.89 | 3,674.65 | 406.95 | 3,485.93 | 6.33 | 100.33 | False/False |
| 18 | 932.59 | 1,107.44 | 323.91 | 3,496.10 | 10.74 | 76.56 | False/False |
| 19 | 3,609.27 | 1,308.30 | 349.98 | 3,694.29 | 6.02 | 111.43 | False/False |
| 20 | 1,397.50 | 882.99 | 370.16 | 3,837.44 | 5.08 | 108.02 | False/False |
| 21 | 896.07 | 1,292.71 | 369.17 | 3,566.24 | 5.75 | 134.85 | False/False |
| 22 | 1,181.50 | 1,362.80 | 147.44 | 3,522.18 | 5.03 | 53.83 | False/False |
| 23 | 2,592.64 | 1,987.47 | 368.25 | 3,587.15 | 2.63 | 160.14 | False/False |
| 24 | 513.29 | 688.26 | — | 295.36 | 0.70 | 0.22 | False/False |
| 25 | 457.44 | 961.29 | 279.61 | 3,145.53 | 3.48 | 122.34 | False/False |
| 26 | 828.77 | 890.43 | 934.68 | 3,105.38 | 2.28 | 135.12 | False/False |
| 27 | — | — | — | — | — | 92.01 | True/False |
| 28 | 545.71 | 1,073.02 | 1,552.37 | 5,393.16 | 287.07 | 210.59 | False/True |
| 29 | 602.35 | 1,034.90 | 1,247.29 | 6,093.67 | 12.24 | 125.45 | False/True |
| 30 | 546.65 | 1,766.46 | 1,854.77 | 3,686.81 | 10.86 | 296.73 | False/True |
| 31 | 657.37 | 1,718.65 | 2,330.36 | 3,312.60 | 2.07 | 320.64 | False/True |
| 32 | 1,679.60 | 1,260.45 | 337.76 | 3,055.20 | 0.28 | 41.53 | False/True |
| 33 | 440.74 | 1,025.73 | 1,616.19 | 3,789.15 | 4.03 | 231.09 | False/True |
| 34 | 449.46 | 982.75 | 1,048.43 | 3,868.55 | 19.24 | 192.80 | False/True |
| 35 | 881.57 | 1,094.10 | 2,116.60 | 4,092.03 | 7.23 | 396.90 | False/True |
| 36 | 321.55 | 930.84 | 1,061.77 | 3,842.30 | 5.00 | 325.56 | False/True |
| 37 | 998.88 | 1,051.32 | 1,482.41 | 3,595.68 | 5.34 | 363.20 | False/True |
| 38 | 350.29 | 898.72 | 644.23 | 3,980.91 | 5.74 | 241.10 | False/True |
| 39 | 1,562.75 | 1,026.18 | 1,560.68 | 3,843.55 | 4.53 | 308.92 | False/True |
| 40 | 1,130.50 | 897.90 | 1,267.22 | 3,804.35 | 7.24 | 328.16 | False/True |
| 41 | 1,202.60 | 3,356.88 | 879.53 | 3,879.96 | 6.46 | 222.11 | False/True |
| 42 | 1,162.57 | 885.75 | 590.19 | 4,275.93 | 7.62 | 283.27 | False/True |
| 43 | 1,095.22 | 990.24 | 501.37 | 4,046.12 | 9.39 | 329.25 | False/True |
| 44 | 526.91 | 959.15 | 737.75 | 3,631.79 | 7.28 | 256.53 | False/True |
| 45 | 836.10 | 841.80 | 383.44 | 3,846.18 | 9.03 | 247.20 | False/True |
| 46 | 564.84 | 936.27 | 1,198.55 | 3,517.51 | 4.46 | 438.15 | False/True |
| 47 | 652.76 | 1,203.94 | 1,608.81 | 3,887.66 | 9.15 | 514.61 | False/True |
| 48 | 559.20 | 925.14 | 555.28 | 3,746.17 | 13.88 | 275.22 | False/True |
| 49 | 1,090.31 | 1,420.13 | 1,128.03 | 3,665.89 | 6.12 | 358.87 | False/True |
| 50 | 899.16 | 1,438.94 | 442.69 | 4,343.54 | 8.62 | 265.17 | False/True |
| 51 | 3,279.42 | 1,005.44 | 665.23 | 3,977.13 | 8.75 | 275.35 | False/True |
| 52 | 837.60 | 884.55 | 539.29 | 3,570.51 | 5.73 | 162.75 | False/True |
| 53 | 588.73 | 852.76 | 443.52 | 2,099.52 | 2.59 | 138.65 | False/True |
| 54 | 382.43 | 1,131.76 | — | 1,379.70 | 2.40 | 0.09 | False/True |
| 55 | 844.56 | 908.92 | 369.58 | 3,753.51 | 7.80 | 190.58 | False/True |
| 56 | 1,847.51 | 1,160.21 | 609.14 | 2,596.30 | 0.52 | 183.61 | False/True |
| 57 | 925.53 | 1,012.35 | 622.13 | 3,714.69 | 5.83 | 179.94 | False/True |
| 58 | 361.74 | 869.84 | 1,014.49 | 3,470.88 | 8.98 | 294.91 | False/True |
| 59 | 1,010.14 | 2,256.35 | 1,282.25 | 4,139.82 | 9.13 | 497.35 | False/True |
| 60 | 917.25 | 1,120.99 | 628.79 | 4,178.39 | 10.54 | 236.89 | False/True |
| 61 | 770.38 | 1,041.52 | 871.16 | 4,043.99 | 12.82 | 359.74 | False/True |
| 62 | 356.51 | 1,136.95 | 478.78 | 4,260.80 | 12.07 | 382.83 | False/True |
| 63 | 1,032.04 | 1,107.35 | 188.46 | 4,347.57 | 11.18 | 62.32 | False/True |
| 64 | 1,579.58 | 1,196.25 | 1,145.04 | 4,313.79 | 29.58 | 379.62 | False/True |
| 65 | 1,111.21 | 123,525.17 | 1,085.24 | 3,074.29 | 5.66 | 349.62 | False/True |
| 66 | 496.16 | 1,019.65 | 1,314.32 | 3,816.14 | 11.41 | 544.95 | False/True |
| 67 | 1,152.65 | 124,880.27 | 890.27 | 3,712.65 | 3.75 | 451.22 | False/True |
| 68 | 6,305.13 | 963.50 | 1,054.15 | 3,455.42 | 2.04 | 353.14 | False/True |
| 69 | 533.73 | 1,648.93 | 218.49 | 3,492.38 | 1.14 | 71.74 | False/True |
| 70 | 735.60 | 1,080.41 | 374.50 | 955.19 | 0.06 | 143.40 | False/True |
| 71 | 746.62 | 561.92 | — | 2,772.07 | 1.38 | 0.09 | False/True |
| 72 | 1,402.46 | 835.20 | 181.34 | 3,378.48 | 0.23 | 79.51 | False/True |
| 73 | 6,281.92 | 967.77 | 343.47 | 3,491.19 | 4.33 | 158.32 | False/True |
| 74 | 869.13 | 1,829.24 | 407.79 | 4,353.44 | 6.72 | 139.05 | False/True |
| 75 | 968.76 | 899.32 | 1,114.42 | 4,302.22 | 6.79 | 376.43 | False/True |
| 76 | 884.27 | 1,233.11 | 2,240.20 | 4,234.26 | 6.26 | 793.37 | False/True |
| 77 | 1,047.32 | 1,005.74 | 760.97 | 4,514.89 | 7.44 | 217.93 | False/True |
| 78 | 957.56 | 1,058.66 | 736.47 | 4,135.89 | 7.79 | 215.08 | False/True |
| 79 | 947.74 | 1,067.10 | 483.99 | 4,281.54 | 6.37 | 145.92 | False/True |
| 80 | 236.92 | 1,188.10 | 1,253.06 | 4,406.00 | 8.99 | 443.70 | False/True |
| 81 | 279.16 | 1,168.87 | 2,090.36 | 4,433.69 | 7.39 | 737.24 | False/True |
| 82 | 599.48 | 830.16 | 670.03 | 3,995.38 | 6.97 | 267.33 | False/True |
| 83 | 1,044.94 | 956.59 | 2,616.96 | 4,569.46 | 7.24 | 987.86 | False/True |
| 84 | 892.36 | 1,191.36 | 743.06 | 3,929.30 | 4.42 | 322.20 | False/True |
| 85 | 237.64 | 1,003.35 | 1,220.59 | 4,204.26 | 21.08 | 484.91 | False/True |
| 86 | 822.83 | 1,039.65 | 1,320.27 | 4,161.49 | 8.61 | 485.60 | False/True |
| 87 | 735.64 | 1,419.01 | 1,534.52 | 4,030.67 | 8.59 | 730.69 | False/True |
| 88 | 936.75 | 871.48 | 1,221.62 | 4,264.76 | 10.28 | 505.75 | False/True |
| 89 | 999.60 | 1,060.23 | 1,002.10 | 3,605.11 | 8.14 | 425.58 | False/True |
| 90 | 1,164.67 | 1,768.13 | 1,322.65 | 3,577.46 | 8.29 | 776.66 | False/True |
| 91 | 899.58 | 987.30 | 535.83 | 3,907.72 | 10.94 | 268.54 | False/True |
| 92 | 985.85 | 991.11 | 1,230.98 | 4,268.28 | 9.53 | 543.38 | False/True |
| 93 | 1,772.20 | 1,310.46 | 1,993.75 | 3,937.06 | 9.03 | 949.89 | False/True |
| 94 | 1,809.44 | 1,278.85 | 1,539.05 | 3,834.85 | 23.90 | 718.93 | False/True |
| 95 | 1,518.02 | 1,191.90 | 1,523.41 | 3,870.04 | 6.88 | 817.62 | False/True |
| 96 | 270.20 | 1,119.41 | 262.69 | 4,063.48 | 9.59 | 431.28 | False/True |
| 97 | 868.41 | 1,155.11 | 758.67 | 3,711.19 | 8.95 | 471.51 | False/True |
| 98 | 388.05 | 121,696.93 | — | 1,909.20 | 0.26 | 0.21 | False/True |
| 99 | 1.93 | 2.19 | 1,290.00 | 3,835.87 | 8.18 | 539.28 | False/True |
| 100 | 958.21 | 1,164.57 | 1,756.67 | 3,860.22 | 6.83 | 865.25 | False/True |
| 101 | 1,014.11 | 1,371.69 | 342.69 | 799.91 | 3.38 | 112.70 | False/True |
| 102 | 6,179.85 | 891.19 | 923.71 | 3,385.92 | 7.94 | 384.91 | False/True |
| 103 | 943.61 | 1,091.89 | 974.67 | 4,182.70 | 9.02 | 383.07 | False/True |
| 104 | 957.71 | 1,025.73 | 948.37 | 3,740.39 | 5.62 | 487.10 | False/True |
| 105 | 957.89 | 2,102.66 | 2,207.60 | 3,432.06 | 9.51 | 1,068.51 | False/True |
| 106 | 1,757.97 | 1,051.38 | 2,440.36 | 3,980.34 | 8.74 | 1,560.45 | False/True |
| 107 | 871.80 | 1,825.11 | 2,184.63 | 3,967.59 | 9.60 | 1,121.43 | False/True |
| 108 | 1,338.76 | 3,166.87 | 1,430.24 | 3,984.00 | 7.21 | 720.82 | False/True |
| 109 | 319.73 | 1,019.36 | 1,540.76 | 4,501.23 | 11.12 | 925.72 | False/True |
| 110 | 1,319.44 | 1,692.43 | 1,180.88 | 4,320.54 | 8.77 | 603.24 | False/True |
| 111 | 635.38 | 949.72 | 997.77 | 4,537.85 | 11.11 | 526.55 | False/True |
| 112 | 169.97 | 784.78 | — | 851.27 | 1.77 | 0.10 | False/True |
| 113 | 850.52 | 974.52 | 439.81 | 3,383.46 | 4.78 | 231.19 | False/True |
| 114 | 1,225.64 | 1,158.07 | 1,231.48 | 3,946.87 | 4.24 | 563.95 | False/True |
| 115 | 910.97 | 1,053.92 | 1,301.59 | 3,949.57 | 3.47 | 642.02 | False/True |
| 116 | 401.93 | 871.25 | 762.85 | 3,715.35 | 3.94 | 341.73 | False/True |
| 117 | 1,203.13 | 1,054.29 | 1,255.82 | 3,685.57 | 2.04 | 664.07 | False/True |
| 118 | 469.08 | 1,154.31 | 892.50 | 3,640.63 | 3.24 | 440.88 | False/True |
| 119 | 853.55 | 1,002.88 | 1,546.32 | 3,617.63 | 2.87 | 776.72 | False/True |
| 120 | 553.16 | 1,156.19 | 1,775.23 | 3,283.98 | 1.42 | 1,010.38 | False/True |
| 121 | 890.71 | 1,002.90 | 1,239.20 | 3,801.15 | 1.86 | 580.39 | False/True |
| 122 | 925.89 | 1,046.68 | 954.17 | 3,945.72 | 3.77 | 549.90 | False/True |
| 123 | 887.55 | 916.04 | 1,489.65 | 3,475.30 | 2.17 | 829.49 | False/True |
| 124 | 290.15 | 1,015.37 | 2,036.05 | 4,099.55 | 5.71 | 2,113.75 | False/True |
| 125 | 1,033.94 | 1,064.29 | 2,963.10 | 4,212.39 | 7.89 | 1,668.82 | False/True |
| 126 | 821.77 | 982.54 | 1,869.91 | 4,142.02 | 7.61 | 1,107.15 | False/True |
| 127 | 1,267.60 | 1,125.95 | 3,427.97 | 3,886.32 | 6.96 | 2,145.56 | False/True |
| 128 | 308.48 | 1,125.19 | 775.62 | 1,594.78 | 2.53 | 521.55 | False/True |
| 129 | 656.40 | 1,377.60 | 1,253.40 | 2,599.40 | 10.45 | 777.47 | False/True |
| 130 | 286.17 | 1,128.94 | 2,648.29 | 3,926.84 | 6.16 | 1,966.73 | False/True |
| 131 | 952.05 | 1,101.19 | 535.68 | 4,401.89 | 6.73 | 267.12 | False/True |
| 132 | 860.82 | 981.23 | 252.56 | 1,751.78 | 2.26 | 135.07 | False/True |
| 133 | 270.98 | 1,117.85 | 1,224.42 | 2,717.99 | 5.49 | 756.53 | False/True |
| 134 | 259.00 | 948.28 | 1,252.44 | 4,993.36 | 9.74 | 789.92 | False/True |
| 135 | 550.97 | 960.84 | 2,353.04 | 4,914.45 | 28.64 | 1,560.79 | False/True |
| 136 | 1,022.19 | 871.89 | 1,093.60 | 4,429.53 | 6.52 | 671.09 | False/True |
| 137 | 908.43 | 1,289.14 | 2,846.68 | 5,012.31 | 26.15 | 2,355.95 | False/True |
| 138 | 2,210.98 | 1,091.60 | 2,385.58 | 4,070.61 | 9.75 | 3,065.13 | False/True |
| 139 | 373.18 | 1,026.80 | 2,056.89 | 4,468.66 | 499.68 | 1,463.46 | False/True |
| 140 | 659.02 | 1,046.24 | 1,703.76 | 4,323.50 | 6.04 | 1,325.28 | False/True |
| 141 | 902.45 | 969.87 | 1,686.79 | 4,176.39 | 7.55 | 1,129.17 | False/True |
| 142 | 1,104.32 | 1,002.31 | 1,473.70 | 4,204.51 | 5.07 | 992.34 | False/True |
| 143 | 624.91 | 1,386.14 | 1,453.22 | 4,443.13 | 8.06 | 1,073.68 | False/True |
| 144 | 295.20 | 1,280.89 | 1,402.51 | 4,099.42 | 26.98 | 1,059.72 | False/True |

ASR provider times can overlap; the ASR-stage column above is independently measured wall time. An ASR cache hit is not a new provider-speed measurement.

## Per-clip embedding batches

| Segment | Texts | Whole batch ms | Tokens | API attempts |
| --- | --- | --- | --- | --- |
| 27 | 9 | 869.09 | 161 | 1 |
| 28 | 9 | 501.64 | 156 | 1 |
| 29 | 9 | 881.89 | 171 | 1 |
| 30 | 17 | 549.02 | 298 | 1 |
| 31 | 8 | 484.95 | 127 | 1 |
| 32 | 8 | 499.13 | 127 | 1 |
| 33 | 6 | 499.52 | 115 | 1 |
| 34 | 9 | 1,257.82 | 146 | 1 |
| 35 | 16 | 860.95 | 237 | 1 |
| 36 | 10 | 477.26 | 171 | 1 |
| 37 | 7 | 512.39 | 197 | 1 |
| 38 | 9 | 705.47 | 183 | 1 |
| 39 | 9 | 363.71 | 154 | 1 |
| 40 | 6 | 642.90 | 114 | 1 |
| 41 | 12 | 615.86 | 254 | 1 |
| 42 | 8 | 582.14 | 171 | 1 |
| 43 | 7 | 562.38 | 122 | 1 |
| 44 | 10 | 661.16 | 174 | 1 |
| 45 | 11 | 479.40 | 179 | 1 |
| 46 | 7 | 372.40 | 108 | 1 |
| 47 | 7 | 378.62 | 131 | 1 |
| 48 | 6 | 439.46 | 99 | 1 |
| 49 | 8 | 441.51 | 163 | 1 |
| 50 | 9 | 521.45 | 181 | 1 |
| 51 | 11 | 420.91 | 201 | 1 |
| 52 | 10 | 384.56 | 196 | 1 |
| 53 | 8 | 515.85 | 177 | 1 |
| 54 | 8 | 399.39 | 134 | 1 |
| 55 | 10 | 490.05 | 189 | 1 |
| 56 | 6 | 409.74 | 110 | 1 |
| 57 | 11 | 465.86 | 243 | 1 |
| 58 | 9 | 541.35 | 171 | 1 |
| 59 | 8 | 522.31 | 141 | 1 |
| 60 | 8 | 1,676.70 | 161 | 1 |
| 61 | 9 | 521.06 | 158 | 1 |
| 62 | 10 | 538.00 | 188 | 1 |
| 63 | 7 | 393.01 | 161 | 1 |
| 64 | 10 | 449.04 | 188 | 1 |
| 65 | 9 | 1,547.38 | 211 | 1 |
| 66 | 11 | 555.80 | 182 | 1 |
| 67 | 15 | 624.21 | 293 | 1 |
| 68 | 13 | 421.85 | 223 | 1 |
| 69 | 7 | 592.92 | 114 | 1 |
| 70 | 8 | 416.70 | 138 | 1 |
| 71 | 10 | 552.76 | 215 | 1 |
| 72 | 6 | 465.56 | 90 | 1 |
| 73 | 14 | 565.22 | 267 | 1 |
| 74 | 12 | 575.24 | 232 | 1 |
| 75 | 9 | 532.61 | 174 | 1 |
| 76 | 9 | 411.82 | 174 | 1 |
| 77 | 8 | 513.92 | 169 | 1 |
| 78 | 11 | 653.63 | 220 | 1 |
| 79 | 12 | 585.92 | 276 | 1 |
| 80 | 11 | 384.97 | 196 | 1 |
| 81 | 8 | 646.31 | 170 | 1 |
| 82 | 10 | 617.48 | 176 | 1 |
| 83 | 10 | 409.63 | 173 | 1 |
| 84 | 13 | 746.74 | 200 | 1 |
| 85 | 12 | 566.01 | 311 | 1 |
| 86 | 8 | 418.91 | 157 | 1 |
| 87 | 7 | 525.54 | 124 | 1 |
| 88 | 11 | 460.45 | 207 | 1 |
| 89 | 7 | 509.06 | 119 | 1 |
| 90 | 8 | 868.59 | 122 | 1 |
| 91 | 10 | 449.52 | 234 | 1 |
| 92 | 9 | 340.18 | 185 | 1 |
| 93 | 9 | 580.05 | 173 | 1 |
| 94 | 11 | 459.31 | 223 | 1 |
| 95 | 10 | 410.21 | 207 | 1 |
| 96 | 10 | 580.39 | 175 | 1 |
| 97 | 8 | 1,059.57 | 182 | 1 |
| 98 | 6 | 656.28 | 106 | 1 |
| 99 | 14 | 655.42 | 258 | 1 |
| 100 | 10 | 477.43 | 189 | 1 |
| 101 | 8 | 570.09 | 167 | 1 |
| 102 | 7 | 486.27 | 154 | 1 |
| 103 | 10 | 506.15 | 167 | 1 |
| 104 | 8 | 767.13 | 179 | 1 |
| 105 | 14 | 685.65 | 319 | 1 |
| 106 | 15 | 581.23 | 286 | 1 |
| 107 | 10 | 616.91 | 180 | 1 |
| 108 | 8 | 542.26 | 163 | 1 |
| 109 | 10 | 449.04 | 213 | 1 |
| 110 | 10 | 550.86 | 242 | 1 |
| 111 | 8 | 421.18 | 150 | 1 |
| 112 | 9 | 435.02 | 157 | 1 |
| 113 | 8 | 539.89 | 182 | 1 |
| 114 | 14 | 571.77 | 295 | 1 |
| 115 | 9 | 590.38 | 148 | 1 |
| 116 | 10 | 611.18 | 181 | 1 |
| 117 | 11 | 591.59 | 228 | 1 |
| 118 | 10 | 541.17 | 188 | 1 |
| 119 | 9 | 471.78 | 163 | 1 |
| 120 | 8 | 509.48 | 125 | 1 |
| 121 | 9 | 476.00 | 173 | 1 |
| 122 | 8 | 465.41 | 113 | 1 |
| 123 | 13 | 491.03 | 251 | 1 |
| 124 | 14 | 493.44 | 301 | 1 |
| 125 | 8 | 483.78 | 173 | 1 |
| 126 | 7 | 549.34 | 126 | 1 |
| 127 | 12 | 661.17 | 243 | 1 |
| 128 | 6 | 755.65 | 96 | 1 |
| 129 | 6 | 1,320.33 | 116 | 1 |
| 130 | 9 | 564.07 | 161 | 1 |
| 131 | 9 | 420.83 | 169 | 1 |
| 132 | 6 | 301.43 | 113 | 1 |
| 133 | 8 | 518.68 | 147 | 1 |
| 134 | 8 | 522.11 | 148 | 1 |
| 135 | 11 | 579.86 | 257 | 1 |
| 136 | 10 | 501.59 | 201 | 1 |
| 137 | 13 | 578.74 | 225 | 1 |
| 138 | 8 | 620.09 | 186 | 1 |
| 139 | 7 | 528.35 | 134 | 1 |
| 140 | 10 | 950.63 | 227 | 1 |
| 141 | 11 | 663.75 | 241 | 1 |
| 142 | 11 | 353.48 | 253 | 1 |
| 143 | 13 | 523.32 | 275 | 1 |
| 144 | 11 | 608.44 | 200 | 1 |

Each input retains its own vector. Individual-text latency is unavailable; batch time is not divided by text count.

## Timing-policy boundaries

| First segment | ASR | HTTP | Embedding | Lookahead |
| --- | --- | --- | --- | --- |
| 27 | concurrent providers | persistent per-process pools with TCP/TLS event counts | one batch per clip; per-text latency unavailable | 2 |

## QA measurements

| Q | Method | Mode | Retrieval requests | Reasoning calls | Retrieval total | Reasoning total | Question → answer | Answer | Correct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | A | warm_retrieval_uncached_question | 4 | 6 | 1,448.99 | 49,965.25 | 51,417.21 | C | False |
| 2 | A | warm_retrieval_uncached_question | 4 | 6 | 1,502.91 | 58,206.15 | 59,712.18 | C | True |
| 3 | A | warm_retrieval_uncached_question | 4 | 6 | 2,265.06 | 88,471.81 | 90,739.85 | A | False |
| 4 | A | warm_retrieval_uncached_question | 4 | 6 | 1,836.28 | 128,827.30 | 130,666.79 | B | False |
| 5 | A | warm_retrieval_uncached_question | 4 | 6 | 2,197.30 | 46,680.52 | 48,881.10 | A | False |
| 6 | A | warm_retrieval_uncached_question | 4 | 6 | 1,704.30 | 91,564.67 | 93,272.18 | D | True |
| 7 | A | warm_retrieval_uncached_question | 4 | 6 | 1,641.08 | 103,767.02 | 105,411.29 | C | True |
| 8 | A | warm_retrieval_uncached_question | 4 | 6 | 1,958.20 | 216,092.67 | 218,054.26 | A | False |
| 9 | A | warm_retrieval_uncached_question | 4 | 6 | 1,839.36 | 120,846.38 | 122,689.02 | B | False |
| 10 | A | warm_retrieval_uncached_question | 4 | 6 | 2,438.98 | 111,517.98 | 113,960.28 | A | True |
| 1 | B | warm_retrieval_uncached_question | 1 | 1 | 289.06 | 51,161.24 | 51,450.96 | D | False |
| 2 | B | warm_retrieval_uncached_question | 1 | 1 | 325.21 | 13,301.95 | 13,627.75 | B | False |
| 3 | B | warm_retrieval_uncached_question | 1 | 1 | 658.61 | 20,580.24 | 21,239.40 | B | False |
| 4 | B | warm_retrieval_uncached_question | 1 | 1 | 494.40 | 63,205.99 | 63,700.92 | C | True |
| 5 | B | warm_retrieval_uncached_question | 1 | 1 | 338.44 | 154,403.76 | 154,742.74 | A | False |
| 6 | B | warm_retrieval_uncached_question | 1 | 1 | 394.68 | 13,806.01 | 14,201.20 | D | True |
| 7 | B | warm_retrieval_uncached_question | 1 | 1 | 496.12 | 6,567.29 | 7,064.00 | C | True |
| 8 | B | warm_retrieval_uncached_question | 1 | 1 | 386.08 | 13,706.66 | 14,093.30 | C | False |
| 9 | B | warm_retrieval_uncached_question | 1 | 1 | 460.34 | 9,672.96 | 10,133.90 | A | False |
| 10 | B | warm_retrieval_uncached_question | 1 | 1 | 587.55 | 13,780.00 | 14,368.13 | A | True |
| 1 | C | warm_retrieval_uncached_question | 1 | 1 | 332.00 | 15,364.40 | 15,697.15 | D | False |
| 2 | C | warm_retrieval_uncached_question | 1 | 1 | 398.26 | 59,648.16 | 60,047.06 | C | True |
| 3 | C | warm_retrieval_uncached_question | 1 | 1 | 552.08 | 14,600.32 | 15,152.97 | D | True |
| 4 | C | warm_retrieval_uncached_question | 1 | 1 | 296.67 | 12,973.60 | 13,270.92 | C | True |
| 5 | C | warm_retrieval_uncached_question | 1 | 1 | 300.97 | 12,379.97 | 12,681.49 | A | False |
| 6 | C | warm_retrieval_uncached_question | 1 | 1 | 333.54 | 13,623.18 | 13,957.30 | D | True |
| 7 | C | warm_retrieval_uncached_question | 1 | 1 | 478.59 | 10,607.49 | 11,086.60 | C | True |
| 8 | C | warm_retrieval_uncached_question | 1 | 1 | 338.02 | 7,685.58 | 8,024.11 | C | False |
| 9 | C | warm_retrieval_uncached_question | 1 | 1 | 372.97 | 14,787.23 | 15,160.80 | B | False |
| 10 | C | warm_retrieval_uncached_question | 1 | 1 | 429.76 | 6,699.51 | 7,129.78 | A | True |
| 1 | D | warm_retrieval_uncached_question | 1 | 1 | 2,853.55 | 15,573.97 | 18,429.13 | D | False |
| 2 | D | warm_retrieval_uncached_question | 1 | 1 | 2,473.80 | 3,911.19 | 6,385.97 | C | True |
| 3 | D | warm_retrieval_uncached_question | 1 | 1 | 2,438.22 | 4,804.27 | 7,244.66 | D | True |
| 4 | D | warm_retrieval_uncached_question | 1 | 1 | 2,336.67 | 17,365.54 | 19,704.35 | D | False |
| 5 | D | warm_retrieval_uncached_question | 1 | 1 | 2,294.26 | 13,766.76 | 16,062.06 | A | False |
| 6 | D | warm_retrieval_uncached_question | 1 | 1 | 2,244.86 | 23,074.46 | 25,322.00 | C | False |
| 7 | D | warm_retrieval_uncached_question | 1 | 1 | 2,476.60 | 16,429.16 | 18,906.79 | C | True |
| 8 | D | warm_retrieval_uncached_question | 1 | 1 | 2,255.19 | 9,247.70 | 11,504.88 | C | False |
| 9 | D | warm_retrieval_uncached_question | 1 | 1 | 2,213.12 | 52,475.00 | 54,690.21 | B | False |
| 10 | D | warm_retrieval_uncached_question | 1 | 1 | 2,413.50 | 5,874.93 | 8,290.57 | A | True |

### Retrieval-stage detail

| Q/method/round | Embedding | Dense | Sparse | StreamMeCo scoring | Fusion | Lookup | Rerank | Total |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1/A/1 | 259.07 | 28.18 | 0.00 | 0.19 | — | 0.47 | 0.00 | 288.32 |
| 1/A/2 | 384.62 | 28.89 | 0.00 | 0.23 | — | 0.30 | 0.00 | 414.49 |
| 1/A/3 | 324.15 | 27.63 | 0.00 | 0.22 | — | 0.06 | 0.00 | 352.50 |
| 1/A/4 | 365.11 | 27.84 | 0.00 | 0.22 | — | 0.06 | 0.00 | 393.68 |
| 2/A/1 | 228.84 | 57.95 | 0.00 | 0.51 | — | 0.71 | 0.00 | 288.55 |
| 2/A/2 | 257.19 | 59.48 | 0.00 | 0.56 | — | 0.59 | 0.00 | 318.36 |
| 2/A/3 | 390.64 | 58.49 | 0.00 | 0.60 | — | 0.42 | 0.00 | 450.89 |
| 2/A/4 | 376.74 | 67.04 | 0.00 | 0.54 | — | 0.14 | 0.00 | 445.11 |
| 3/A/1 | 988.38 | 58.70 | 0.00 | 0.48 | — | 0.70 | 0.00 | 1,048.93 |
| 3/A/2 | 224.46 | 60.33 | 0.00 | 0.50 | — | 0.61 | 0.00 | 286.47 |
| 3/A/3 | 404.32 | 57.76 | 0.00 | 0.54 | — | 0.46 | 0.00 | 463.62 |
| 3/A/4 | 404.50 | 60.06 | 0.00 | 0.58 | — | 0.14 | 0.00 | 466.05 |
| 4/A/1 | 582.25 | 78.11 | 0.00 | 0.76 | — | 0.92 | 0.00 | 662.65 |
| 4/A/2 | 379.23 | 85.42 | 0.00 | 0.80 | — | 0.76 | 0.00 | 466.84 |
| 4/A/3 | 273.60 | 84.94 | 0.00 | 0.79 | — | 0.62 | 0.00 | 360.58 |
| 4/A/4 | 261.15 | 83.25 | 0.00 | 0.75 | — | 0.47 | 0.00 | 346.22 |
| 5/A/1 | 410.34 | 112.14 | 0.00 | 0.92 | — | 1.24 | 0.00 | 525.33 |
| 5/A/2 | 356.90 | 405.58 | 0.00 | 2.90 | — | 1.15 | 0.00 | 767.43 |
| 5/A/3 | 272.78 | 148.86 | 0.00 | 1.88 | — | 0.94 | 0.00 | 425.27 |
| 5/A/4 | 364.84 | 111.92 | 0.00 | 1.01 | — | 0.77 | 0.00 | 479.27 |
| 6/A/1 | 338.20 | 107.15 | 0.00 | 0.98 | — | 1.24 | 0.00 | 448.32 |
| 6/A/2 | 242.26 | 108.31 | 0.00 | 0.98 | — | 1.07 | 0.00 | 353.34 |
| 6/A/3 | 353.94 | 108.77 | 0.00 | 1.07 | — | 0.96 | 0.00 | 465.59 |
| 6/A/4 | 322.85 | 111.64 | 0.00 | 1.03 | — | 0.80 | 0.00 | 437.05 |
| 7/A/1 | 237.56 | 132.65 | 0.00 | 1.10 | — | 1.36 | 0.00 | 373.45 |
| 7/A/2 | 305.25 | 123.40 | 0.00 | 1.15 | — | 1.23 | 0.00 | 431.86 |
| 7/A/3 | 309.06 | 124.83 | 0.00 | 1.15 | — | 1.09 | 0.00 | 436.97 |
| 7/A/4 | 273.00 | 122.86 | 0.00 | 1.17 | — | 0.95 | 0.00 | 398.81 |
| 8/A/1 | 295.53 | 145.33 | 0.00 | 1.35 | — | 1.78 | 0.00 | 444.84 |
| 8/A/2 | 347.72 | 157.88 | 0.00 | 1.35 | — | 1.40 | 0.00 | 509.23 |
| 8/A/3 | 361.74 | 154.96 | 0.00 | 1.37 | — | 1.29 | 0.00 | 520.31 |
| 8/A/4 | 323.09 | 153.28 | 0.00 | 1.39 | — | 1.11 | 0.00 | 483.82 |
| 9/A/1 | 277.65 | 157.42 | 0.00 | 1.46 | — | 2.03 | 0.00 | 439.50 |
| 9/A/2 | 312.38 | 153.81 | 0.00 | 1.43 | — | 1.42 | 0.00 | 469.94 |
| 9/A/3 | 297.97 | 162.46 | 0.00 | 1.41 | — | 1.31 | 0.00 | 464.10 |
| 9/A/4 | 311.51 | 150.91 | 0.00 | 1.35 | — | 1.16 | 0.00 | 465.82 |
| 10/A/1 | 437.08 | 183.26 | 0.00 | 1.46 | — | 1.71 | 0.00 | 624.50 |
| 10/A/2 | 341.08 | 172.66 | 0.00 | 1.57 | — | 2.04 | 0.00 | 518.38 |
| 10/A/3 | 455.60 | 178.49 | 0.00 | 1.71 | — | 1.71 | 0.00 | 638.55 |
| 10/A/4 | 474.67 | 178.57 | 0.00 | 1.69 | — | 1.56 | 0.00 | 657.55 |
| 1/B/1 | 262.03 | 26.05 | 0.00 | 0.20 | — | 0.43 | 0.00 | 289.06 |
| 2/B/1 | 260.28 | 63.05 | 0.00 | 0.67 | — | 0.71 | 0.00 | 325.21 |
| 3/B/1 | 593.55 | 63.38 | 0.00 | 0.48 | — | 0.71 | 0.00 | 658.61 |
| 4/B/1 | 412.77 | 79.43 | 0.00 | 0.71 | — | 0.89 | 0.00 | 494.40 |
| 5/B/1 | 221.17 | 114.28 | 0.00 | 1.03 | — | 1.24 | 0.00 | 338.44 |
| 6/B/1 | 283.25 | 108.39 | 0.00 | 1.06 | — | 1.21 | 0.00 | 394.68 |
| 7/B/1 | 286.09 | 207.16 | 0.00 | 0.94 | — | 1.20 | 0.00 | 496.12 |
| 8/B/1 | 235.13 | 147.14 | 0.00 | 1.26 | — | 1.72 | 0.00 | 386.08 |
| 9/B/1 | 284.12 | 172.26 | 0.00 | 1.36 | — | 1.74 | 0.00 | 460.34 |
| 10/B/1 | 400.06 | 183.37 | 0.00 | 1.48 | — | 1.66 | 0.00 | 587.55 |
| 1/C/1 | 308.96 | 22.07 | 0.00 | 0.16 | — | 0.42 | 0.00 | 332.00 |
| 2/C/1 | 350.45 | 45.92 | 0.00 | 0.47 | — | 0.77 | 0.00 | 398.26 |
| 3/C/1 | 504.69 | 45.76 | 0.00 | 0.44 | — | 0.62 | 0.00 | 552.08 |
| 4/C/1 | 228.95 | 65.69 | 0.00 | 0.62 | — | 0.79 | 0.00 | 296.67 |
| 5/C/1 | 219.35 | 79.04 | 0.00 | 0.83 | — | 1.08 | 0.00 | 300.97 |
| 6/C/1 | 241.01 | 89.86 | 0.00 | 0.94 | — | 1.09 | 0.00 | 333.54 |
| 7/C/1 | 377.21 | 98.52 | 0.00 | 0.99 | — | 1.16 | 0.00 | 478.59 |
| 8/C/1 | 223.82 | 111.19 | 0.00 | 0.98 | — | 1.31 | 0.00 | 338.02 |
| 9/C/1 | 258.99 | 110.79 | 0.00 | 1.09 | — | 1.35 | 0.00 | 372.97 |
| 10/C/1 | 309.22 | 117.08 | 0.00 | 1.24 | — | 1.43 | 0.00 | 429.76 |
| 1/D/1 | 1,198.89 | 7.11 | 18.02 | 0.00 | 0.41 | 0.77 | 1,640.97 | 2,853.55 |
| 2/D/1 | 782.15 | 2.70 | 19.97 | 0.00 | 0.56 | 1.34 | 1,680.16 | 2,473.80 |
| 3/D/1 | 733.67 | 5.58 | 22.10 | 0.00 | 0.55 | 1.88 | 1,687.70 | 2,438.22 |
| 4/D/1 | 707.21 | 6.20 | 19.67 | 0.00 | 0.53 | 1.33 | 1,612.37 | 2,336.67 |
| 5/D/1 | 722.15 | 5.89 | 24.30 | 0.00 | 0.56 | 1.81 | 1,551.19 | 2,294.26 |
| 6/D/1 | 614.31 | 6.47 | 19.77 | 0.00 | 0.54 | 1.46 | 1,611.80 | 2,244.86 |
| 7/D/1 | 765.35 | 11.21 | 19.68 | 0.00 | 0.50 | 1.51 | 1,690.65 | 2,476.60 |
| 8/D/1 | 605.82 | 6.22 | 19.34 | 0.00 | 0.44 | 1.11 | 1,629.74 | 2,255.19 |
| 9/D/1 | 607.68 | 6.17 | 19.90 | 0.00 | 0.52 | 1.21 | 1,585.89 | 2,213.12 |
| 10/D/1 | 698.38 | 6.49 | 26.23 | 0.00 | 0.53 | 1.59 | 1,693.66 | 2,413.50 |

### Reasoning calls

| Q/method/call | Purpose | Latency | Input tokens | Output tokens |
| --- | --- | --- | --- | --- |
| 1/A/1 | controller | 4,449.07 | 1253 | 261 |
| 1/A/2 | controller | 5,010.63 | 1868 | 305 |
| 1/A/3 | controller | 7,948.62 | 2399 | 350 |
| 1/A/4 | controller | 17,098.26 | 2490 | 1217 |
| 1/A/5 | controller | 10,846.65 | 2654 | 1170 |
| 1/A/6 | forced_final_answer | 4,612.02 | 1783 | 347 |
| 2/A/1 | controller | 3,589.05 | 1275 | 239 |
| 2/A/2 | controller | 5,562.57 | 1885 | 304 |
| 2/A/3 | controller | 8,563.50 | 2528 | 345 |
| 2/A/4 | controller | 6,482.61 | 3186 | 446 |
| 2/A/5 | controller | 16,638.39 | 3294 | 1688 |
| 2/A/6 | forced_final_answer | 17,370.03 | 2423 | 2297 |
| 3/A/1 | controller | 23,900.24 | 1276 | 155 |
| 3/A/2 | controller | 18,063.00 | 1887 | 342 |
| 3/A/3 | controller | 5,865.02 | 2558 | 439 |
| 3/A/4 | controller | 6,206.90 | 3136 | 395 |
| 3/A/5 | controller | 17,251.97 | 3250 | 740 |
| 3/A/6 | forced_final_answer | 17,184.68 | 2378 | 1129 |
| 4/A/1 | controller | 5,621.87 | 1257 | 254 |
| 4/A/2 | controller | 82,973.80 | 1875 | 489 |
| 4/A/3 | controller | 9,125.09 | 2529 | 275 |
| 4/A/4 | controller | 5,618.72 | 3189 | 444 |
| 4/A/5 | controller | 5,118.21 | 3807 | 348 |
| 4/A/6 | forced_final_answer | 20,369.62 | 2893 | 2652 |
| 5/A/1 | controller | 5,239.64 | 1268 | 211 |
| 5/A/2 | controller | 6,531.54 | 1884 | 351 |
| 5/A/3 | controller | 3,943.22 | 2604 | 269 |
| 5/A/4 | controller | 4,792.89 | 3273 | 256 |
| 5/A/5 | controller | 6,236.79 | 3904 | 253 |
| 5/A/6 | forced_final_answer | 19,936.44 | 2991 | 1267 |
| 6/A/1 | controller | 4,005.21 | 1251 | 173 |
| 6/A/2 | controller | 3,880.58 | 1868 | 301 |
| 6/A/3 | controller | 36,720.22 | 2492 | 585 |
| 6/A/4 | controller | 6,802.80 | 3191 | 571 |
| 6/A/5 | controller | 12,927.92 | 3864 | 343 |
| 6/A/6 | forced_final_answer | 27,227.95 | 2950 | 2303 |
| 7/A/1 | controller | 3,455.09 | 1260 | 226 |
| 7/A/2 | controller | 13,950.37 | 1847 | 320 |
| 7/A/3 | controller | 5,612.02 | 2489 | 359 |
| 7/A/4 | controller | 59,464.58 | 3208 | 326 |
| 7/A/5 | controller | 8,547.64 | 3841 | 569 |
| 7/A/6 | forced_final_answer | 12,737.31 | 2927 | 965 |
| 8/A/1 | controller | 6,585.43 | 1257 | 421 |
| 8/A/2 | controller | 14,267.97 | 1885 | 1682 |
| 8/A/3 | controller | 142,157.34 | 2589 | 169 |
| 8/A/4 | controller | 42,682.25 | 3236 | 510 |
| 8/A/5 | controller | 5,980.30 | 3905 | 382 |
| 8/A/6 | forced_final_answer | 4,419.37 | 2991 | 54 |
| 9/A/1 | controller | 7,645.64 | 1275 | 214 |
| 9/A/2 | controller | 21,396.98 | 1888 | 348 |
| 9/A/3 | controller | 12,100.41 | 2512 | 1324 |
| 9/A/4 | controller | 20,563.21 | 3191 | 470 |
| 9/A/5 | controller | 10,462.36 | 3931 | 288 |
| 9/A/6 | forced_final_answer | 48,677.77 | 3018 | 2747 |
| 10/A/1 | controller | 38,624.24 | 1263 | 180 |
| 10/A/2 | controller | 30,198.37 | 1845 | 281 |
| 10/A/3 | controller | 13,176.17 | 2501 | 349 |
| 10/A/4 | controller | 5,357.02 | 3171 | 403 |
| 10/A/5 | controller | 18,022.48 | 3867 | 435 |
| 10/A/6 | forced_final_answer | 6,139.69 | 2953 | 339 |
| 1/B/1 | final_answer | 51,161.24 | 577 | 1680 |
| 2/B/1 | final_answer | 13,301.95 | 574 | 332 |
| 3/B/1 | final_answer | 20,580.24 | 571 | 1139 |
| 4/B/1 | final_answer | 63,205.99 | 585 | 2576 |
| 5/B/1 | final_answer | 154,403.76 | 608 | 276 |
| 6/B/1 | final_answer | 13,806.01 | 608 | 1418 |
| 7/B/1 | final_answer | 6,567.29 | 566 | 495 |
| 8/B/1 | final_answer | 13,706.66 | 630 | 300 |
| 9/B/1 | final_answer | 9,672.96 | 591 | 989 |
| 10/B/1 | final_answer | 13,780.00 | 547 | 548 |
| 1/C/1 | final_answer | 15,364.40 | 560 | 951 |
| 2/C/1 | final_answer | 59,648.16 | 586 | 235 |
| 3/C/1 | final_answer | 14,600.32 | 600 | 233 |
| 4/C/1 | final_answer | 12,973.60 | 592 | 1418 |
| 5/C/1 | final_answer | 12,379.97 | 614 | 144 |
| 6/C/1 | final_answer | 13,623.18 | 609 | 1567 |
| 7/C/1 | final_answer | 10,607.49 | 558 | 1239 |
| 8/C/1 | final_answer | 7,685.58 | 610 | 301 |
| 9/C/1 | final_answer | 14,787.23 | 590 | 1586 |
| 10/C/1 | final_answer | 6,699.51 | 545 | 431 |
| 1/D/1 | final_answer | 15,573.97 | 8397 | 1521 |
| 2/D/1 | final_answer | 3,911.19 | 8278 | 210 |
| 3/D/1 | final_answer | 4,804.27 | 8396 | 278 |
| 4/D/1 | final_answer | 17,365.54 | 8483 | 1993 |
| 5/D/1 | final_answer | 13,766.76 | 8543 | 1132 |
| 6/D/1 | final_answer | 23,074.46 | 8511 | 2162 |
| 7/D/1 | final_answer | 16,429.16 | 8371 | 487 |
| 8/D/1 | final_answer | 9,247.70 | 8481 | 594 |
| 9/D/1 | final_answer | 52,475.00 | 8488 | 4495 |
| 10/D/1 | final_answer | 5,874.93 | 8442 | 509 |

### Per-method aggregates

| Method | Correct / N | Mean retrieval | Median retrieval | P95 retrieval | Mean QA | Median QA | Mean embedding | Mean model calls |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A | 4 / 10 | 1,883.25 | 1,837.82 | 2,438.98 | 103,480.42 | 99,341.73 | 1,412.72 | 6 |
| B | 4 / 10 | 443.05 | 427.51 | 658.61 | 36,462.23 | 14,284.66 | 323.85 | 1 |
| C | 6 / 10 | 383.29 | 355.49 | 552.08 | 17,220.82 | 13,614.11 | 302.26 | 1 |
| D | 4 / 10 | 2,399.98 | 2,375.08 | 2,853.55 | 18,654.06 | 17,245.59 | 743.56 | 1 |

## Excluded setup / warmup

| Q | Method | Snapshot load | Warmup | Status |
| --- | --- | --- | --- | --- |
| 1 | A | 38.35 | 832.00 | success |
| 2 | A | 88.28 | 373.44 | success |
| 3 | A | 107.36 | 382.18 | success |
| 4 | A | 109.23 | 451.54 | success |
| 5 | A | 174.27 | 422.13 | success |
| 6 | A | 170.55 | 370.94 | success |
| 7 | A | 156.37 | 791.74 | success |
| 8 | A | 189.90 | 499.73 | success |
| 9 | A | 230.66 | 520.60 | success |
| 10 | A | 254.56 | 540.99 | success |
| 1 | B | 39.11 | 553.39 | success |
| 2 | B | 91.04 | 501.46 | success |
| 3 | B | 88.81 | 518.25 | success |
| 4 | B | 93.48 | 431.80 | success |
| 5 | B | 478.70 | 412.54 | success |
| 6 | B | 153.46 | 602.90 | success |
| 7 | B | 166.96 | 417.09 | success |
| 8 | B | 213.23 | 478.96 | success |
| 9 | B | 236.07 | 581.58 | success |
| 10 | B | 251.08 | 557.94 | success |
| 1 | C | 26.27 | 500.12 | success |
| 2 | C | 66.65 | 529.57 | success |
| 3 | C | 69.72 | 453.39 | success |
| 4 | C | 70.91 | 500.92 | success |
| 5 | C | 134.42 | 463.49 | success |
| 6 | C | 407.08 | 490.25 | success |
| 7 | C | 127.59 | 558.64 | success |
| 8 | C | 151.51 | 464.76 | success |
| 9 | C | 163.78 | 448.70 | success |
| 10 | C | 169.10 | 1,114.33 | success |
| 1 | D | 16.05 | 6,401.65 | success |
| 2 | D | 30.07 | 3,044.45 | success |
| 3 | D | 27.36 | 2,905.88 | success |
| 4 | D | 40.07 | 2,835.82 | success |
| 5 | D | 51.77 | 2,888.02 | success |
| 6 | D | 57.52 | 3,230.07 | success |
| 7 | D | 58.51 | 3,025.83 | success |
| 8 | D | 60.12 | 2,761.97 | success |
| 9 | D | 67.93 | 2,846.20 | success |
| 10 | D | 75.67 | 3,034.25 | success |

These are excluded from timed QA calls and warm retrieval latency.

## ASR outcomes

| Provider | Successful API attempts | Failed attempts | Cache hits |
| --- | --- | --- | --- |
| deepgram-asr | 138 | 0 | 1 |
| openrouter-mai-transcribe-2 | 137 | 6 | 1 |

## Failed or degraded processing

| Segment/cache | Status | Error |
| --- | --- | --- |
| /opt/streammeco/run/egolife_10q_gemini/work/intermediate/clip_98_voices.json | partial_asr | ['openrouter-mai-transcribe-2: RuntimeError: ASR provider \'openrouter-mai-transcribe-2\' failed on attempt 2/2: ASRHTTPError: openrouter transcription HTTP 503: {"error":{"message":"Provider returned 503","code":503}}'] |

## Definitions and exact evidence

- [Latency measurement contract](../../scripts/gemini/MEASUREMENT.md)
- [Raw artifacts and logs](../../provenance/raw/gemini)

Warm retrieval excludes snapshot/model/index loading and the unrelated startup probe. It includes the actual question embedding, searches, fusion, lookup and reranking. Warmup is recorded separately, and never primes the benchmark question. Provider-internal model residency cannot be controlled.
