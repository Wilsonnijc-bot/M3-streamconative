# M3-Bench bedroom_01 — Gemini, 15 open-ended questions — latency

Updated: 2026-09-15T02:57:26+00:00. **Complete: 60 verified QA predictions**.

**Method D:** up to **100 candidates → 20 final evidence nodes**, Qwen embedding and reranking via **302.ai**. These are the later rerun measurements; A/B/C retain their original measurements. The earlier two-node D result is retained only in provenance.

## Timing overview

Warm retrieval includes the actual query embedding and all search/rerank work. Index/model loading and the unrelated warmup probe are excluded. Separate semantic grading is excluded from QA timing. Concurrent stages and nested measurements are not additive.

### Parallel execution context

A/B/C/D retain separate per-question and per-round timers. Method locks and process startup occur before snapshot loading/warmup and outside timed QA. Adaptation, warmup, grading and log merging are excluded. Concurrent method durations must not be summed as elapsed benchmark time. Shared GPU/API contention can affect measured latency.

The handover preserved completed answers. Rows not completed at handover are labeled “handover / parallel period”; an already-running question may straddle the boundary. This classification does not claim isolated hardware before the change.

| Method | Period | Answers | Mean retrieval per round ms | Mean full QA ms |
| --- | --- | ---: | ---: | ---: |
| A | Before handover | 15 | 405.96 | 42,374.86 |
| B | Before handover | 2 | 351.02 | 6,202.41 |
| B | Handover / parallel period | 13 | 413.39 | 12,427.37 |
| C | Handover / parallel period | 15 | 470.88 | 7,210.02 |
| D | Later D100/20 rerun | 15 | 2,416.64 | 11,324.82 |

Method-wide statistics below combine these labeled periods; use the split above when comparing scheduling conditions. Exact call timings are retained in the raw per-method rows and telemetry.

### Memory construction: mean and median

| Stage | N | Mean ms | Median ms |
| --- | ---: | ---: | ---: |
| Decode | 76 | 3,598.83 | 3,808.84 |
| Deepgram | 75 | 801.06 | 803.01 |
| MAI | 75 | 1,286.57 | 1,069.49 |
| Concurrent ASR wall time | 75 | 1,405.62 | 1,107.42 |
| CAM++ speaker embedding | 70 | 681.19 | 638.07 |
| Face detection/recognition | 75 | 2,979.08 | 3,217.94 |
| Face clustering | 75 | 8.70 | 7.20 |
| VLM context preparation | 76 | 4,774.04 | 5,000.44 |
| Gemini memory generation | 76 | 47,656.52 | 29,206.82 |
| Whole-clip text embedding batch | 76 | 592.11 | 535.36 |
| Graph update | 76 | 47.59 | 44.80 |

Missing stage values are omitted rather than treated as zero; provider retries remain in measured totals. Per-text latency within a batch is unavailable.

### Method A: warm retrieval per round

| Stage | N | Mean ms | Median ms |
| --- | ---: | ---: | ---: |
| Query text embedding | 43 | 350.61 | 306.04 |
| Dense vector search | 43 | 53.88 | 74.94 |
| Sparse backends (overlap with dense) | 43 | 0.00 | 0.00 |
| StreamMeCo scoring | 43 | 0.47 | 0.65 |
| Node/unit lookup (nested) | 43 | 0.51 | 0.56 |
| Reranker | 43 | 0.00 | 0.00 |
| Total retrieval wall time | 43 | 405.96 | 359.63 |

A can perform multiple retrieval rounds per question; these are per-round statistics. Full QA totals appear below.

### Method B: warm retrieval per round

| Stage | N | Mean ms | Median ms |
| --- | ---: | ---: | ---: |
| Query text embedding | 15 | 333.00 | 299.89 |
| Dense vector search | 15 | 69.94 | 83.53 |
| Sparse backends (overlap with dense) | 15 | 0.00 | 0.00 |
| StreamMeCo scoring | 15 | 0.61 | 0.70 |
| Node/unit lookup (nested) | 15 | 0.96 | 0.94 |
| Reranker | 15 | 0.00 | 0.00 |
| Total retrieval wall time | 15 | 405.08 | 385.71 |

### Method C: warm retrieval per round

| Stage | N | Mean ms | Median ms |
| --- | ---: | ---: | ---: |
| Query text embedding | 15 | 417.86 | 265.82 |
| Dense vector search | 15 | 51.20 | 63.23 |
| Sparse backends (overlap with dense) | 15 | 0.00 | 0.00 |
| StreamMeCo scoring | 15 | 0.51 | 0.64 |
| Node/unit lookup (nested) | 15 | 0.72 | 0.87 |
| Reranker | 15 | 0.00 | 0.00 |
| Total retrieval wall time | 15 | 470.88 | 328.76 |

### Method D: warm retrieval per round

| Stage | N | Mean ms | Median ms |
| --- | ---: | ---: | ---: |
| Query text embedding | 15 | 712.79 | 721.09 |
| Dense vector search | 15 | 5.67 | 5.84 |
| Sparse backends (overlap with dense) | 15 | 20.49 | 19.73 |
| Fusion | 15 | 0.52 | 0.47 |
| Node/unit lookup (nested) | 15 | 0.95 | 1.04 |
| Reranker | 15 | 1,690.05 | 1,642.86 |
| Total retrieval wall time | 15 | 2,416.64 | 2,387.26 |

## Question-level stages: mean and median

Each row below has one observation per answered question. A’s Gemini total includes its final answer; the final-answer row is a subset, not an additional cost.

### Method A: per-question timings

| Stage | N | Mean ms | Median ms |
| --- | ---: | ---: | ---: |
| Retrieval across all rounds | 15 | 1,163.75 | 1,314.78 |
| All Gemini reasoning / answer calls | 15 | 41,209.06 | 31,558.95 |
| Final answer call (included above) | 15 | 8,243.10 | 7,342.96 |
| Full question → answer | 15 | 42,374.86 | 33,049.25 |
| Snapshot loading — excluded | 15 | 85.09 | 101.32 |
| Neutral warmup — excluded | 15 | 1,010.44 | 458.67 |

### Method B: per-question timings

| Stage | N | Mean ms | Median ms |
| --- | ---: | ---: | ---: |
| Retrieval across all rounds | 15 | 405.08 | 385.71 |
| All Gemini reasoning / answer calls | 15 | 11,191.71 | 5,805.13 |
| Final answer call (included above) | 15 | 11,191.71 | 5,805.13 |
| Full question → answer | 15 | 11,597.38 | 6,170.77 |
| Snapshot loading — excluded | 15 | 106.46 | 108.25 |
| Neutral warmup — excluded | 15 | 472.91 | 375.07 |

### Method C: per-question timings

| Stage | N | Mean ms | Median ms |
| --- | ---: | ---: | ---: |
| Retrieval across all rounds | 15 | 470.88 | 328.76 |
| All Gemini reasoning / answer calls | 15 | 6,738.56 | 5,254.33 |
| Final answer call (included above) | 15 | 6,738.56 | 5,254.33 |
| Full question → answer | 15 | 7,210.02 | 5,988.73 |
| Snapshot loading — excluded | 15 | 86.66 | 72.89 |
| Neutral warmup — excluded | 15 | 477.64 | 396.85 |

### Method D: per-question timings

| Stage | N | Mean ms | Median ms |
| --- | ---: | ---: | ---: |
| Retrieval across all rounds | 15 | 2,416.64 | 2,387.26 |
| All Gemini reasoning / answer calls | 15 | 8,906.70 | 7,072.69 |
| Final answer call (included above) | 15 | 8,906.70 | 7,072.69 |
| Full question → answer | 15 | 11,324.82 | 8,752.10 |
| Snapshot loading — excluded | 15 | 31.77 | 33.04 |
| Neutral warmup — excluded | 15 | 3,172.52 | 2,919.44 |

## Offline preparation: mean and median

These are original preparation costs, outside timed QA. The D100/20 rerun reused those indexes. N counts saved per-question preparation records, including repeated query cutoffs.

| Stage | N | Mean ms | Median ms |
| --- | ---: | ---: | ---: |
| Compression | 15 | 1,012.07 | 1,305.77 |
| Mandol export | 15 | 124.25 | 142.11 |
| Mandol build / embedding / sparse index | 15 | 18,083.06 | 22,383.65 |

All values below are measured milliseconds unless stated otherwise. Empty fields mean unavailable, not zero. Overlapping stages must not be added as end-to-end latency. Cached acquisition, warmup, retries and execution-policy changes remain separate.

**Measurement context:** EgoLife Qwen was active on the same A6000 at bedroom setup. Warm local retrieval is measured under observed shared GPU load, not guaranteed isolation.

## Memory construction

| Segment | Nodes | Decode | ASR stage | Reasoning | Text embedding | Ready queue | Ordered processing | Admission → checkpoint |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 10 | 2,689.54 | 987.25 | 20,472.99 | 697.44 | 0.14 | 31,406.27 | 35,163.51 |
| 2 | 21 | 4,521.36 | 1,804.49 | 29,858.57 | 1,765.58 | 0.12 | 41,747.06 | 48,181.27 |
| 3 | 31 | 4,411.87 | 1,043.12 | 77,240.23 | 417.62 | 42,711.55 | 85,435.09 | 133,719.42 |
| 4 | 42 | 4,290.73 | 1,595.94 | 17,265.02 | 507.32 | 127,823.58 | 26,209.13 | 160,062.90 |
| 5 | 50 | 3,108.92 | 542.90 | 18,495.38 | 505.58 | 108,147.32 | 27,251.95 | 139,215.96 |
| 6 | 59 | 3,424.28 | 2,211.53 | 22,928.75 | 376.44 | 47,966.96 | 32,079.99 | 85,909.13 |
| 7 | 67 | 3,108.07 | 1,000.85 | 42,691.10 | 475.54 | 55,428.46 | 51,646.94 | 111,400.55 |
| 8 | 79 | 3,156.66 | 810.44 | 31,073.36 | 490.52 | 80,001.33 | 40,568.19 | 124,775.52 |
| 9 | 87 | 3,236.15 | 950.29 | 39,524.12 | 665.32 | 88,309.18 | 48,979.81 | 141,722.07 |
| 10 | 96 | 3,252.67 | 3,397.83 | 18,313.75 | 528.15 | 83,181.74 | 27,538.37 | 117,662.24 |
| 11 | 108 | 3,149.22 | 1,891.21 | 55,113.01 | 391.60 | 71,815.94 | 63,029.41 | 140,167.91 |
| 12 | 119 | 3,470.91 | 1,107.80 | 47,483.35 | 638.42 | 86,345.91 | 56,582.24 | 147,861.28 |
| 13 | 128 | 4,348.58 | — | 22,952.90 | 625.05 | 0.09 | 28,862.65 | 33,500.08 |
| 14 | 138 | 4,305.86 | 3.47 | 25,688.77 | 631.79 | 29,156.83 | 37,395.56 | 71,200.40 |
| 15 | 147 | 3,039.47 | 1,367.25 | 27,600.54 | 500.32 | 65,660.97 | 31,940.21 | 103,453.28 |
| 16 | 155 | 1,750.66 | 3,054.78 | 14,484.75 | 556.80 | 64,552.31 | 17,431.66 | 88,073.61 |
| 17 | 166 | 3,162.67 | 1,112.04 | 14,575.92 | 706.02 | 46,055.71 | 23,361.41 | 74,076.17 |
| 18 | 179 | 3,218.85 | 956.02 | 38,441.35 | 606.95 | 37,188.20 | 47,589.12 | 89,395.97 |
| 19 | 189 | 3,295.44 | 990.29 | 79,891.16 | 653.14 | 67,293.44 | 89,549.62 | 161,602.87 |
| 20 | 199 | 3,216.38 | 961.51 | 38,536.61 | 488.42 | 133,676.47 | 47,537.67 | 185,908.23 |
| 21 | 208 | 3,605.70 | 970.61 | 21,856.88 | 739.42 | 133,292.16 | 31,580.81 | 169,955.27 |
| 22 | 217 | 3,278.64 | 1,155.63 | 32,839.64 | 466.76 | 75,489.78 | 42,723.95 | 123,145.06 |
| 23 | 230 | 3,479.54 | 1,722.61 | 26,313.87 | 530.15 | 69,897.48 | 35,988.93 | 111,649.50 |
| 24 | 240 | 3,669.33 | 3,502.93 | 132,461.74 | 500.39 | 72,400.87 | 141,930.41 | 222,026.28 |
| 25 | 248 | 1,718.88 | 3,020.17 | 31,566.86 | 405.61 | 173,014.12 | 35,688.58 | 215,074.06 |
| 26 | 260 | 1,563.35 | 761.10 | 80,467.83 | 726.39 | 175,232.49 | 84,427.73 | 263,871.62 |
| 27 | 269 | 3,545.00 | 1,223.83 | 56,662.47 | 555.08 | 116,641.80 | 66,686.27 | 188,703.26 |
| 28 | 281 | 3,399.16 | 883.86 | 27,032.74 | 498.90 | 147,838.64 | 36,773.59 | 189,494.39 |
| 29 | 294 | 3,368.52 | 1,348.95 | 37,265.78 | 600.42 | 99,754.83 | 47,815.39 | 152,927.67 |
| 30 | 301 | 3,173.32 | 979.81 | 20,924.96 | 428.48 | 81,465.67 | 29,996.28 | 116,305.50 |
| 31 | 310 | 3,562.83 | 3,201.85 | 33,196.59 | 1,154.54 | 72,141.30 | 43,673.51 | 123,280.45 |
| 32 | 320 | 3,250.75 | 1,037.00 | 22,584.46 | 478.60 | 70,540.82 | 32,012.72 | 107,571.70 |
| 33 | 331 | 3,575.53 | 965.52 | 28,869.87 | 551.56 | 72,368.69 | 39,248.79 | 116,901.47 |
| 34 | 340 | 3,680.16 | 2,255.18 | 21,359.94 | 527.06 | 66,607.21 | 30,869.91 | 104,154.52 |
| 35 | 350 | 3,825.03 | 1,274.87 | 33,468.58 | 540.40 | 66,315.19 | 43,361.86 | 115,517.89 |
| 36 | 358 | 3,777.02 | 1,134.22 | 59,457.66 | 802.28 | 70,605.70 | 70,181.88 | 146,480.96 |
| 37 | 369 | 3,852.92 | 965.11 | 24,892.86 | 428.58 | 110,048.91 | 34,522.26 | 150,170.02 |
| 38 | 380 | 3,843.09 | 1,075.75 | 56,994.75 | 539.14 | 101,139.12 | 67,551.67 | 174,464.04 |
| 39 | 389 | 4,029.36 | 1,070.82 | 23,073.67 | 499.04 | 98,389.29 | 33,046.77 | 137,354.63 |
| 40 | 398 | 3,838.33 | 1,033.64 | 27,004.42 | 534.39 | 97,130.59 | 37,690.73 | 140,583.54 |
| 41 | 407 | 3,812.90 | 1,103.73 | 24,907.56 | 544.57 | 67,270.51 | 34,802.47 | 107,860.00 |
| 42 | 417 | 3,999.35 | 970.05 | 136,362.04 | 605.91 | 69,038.78 | 146,829.68 | 221,740.03 |
| 43 | 425 | 3,800.86 | 1,080.32 | 30,129.15 | 487.37 | 178,343.68 | 39,428.17 | 223,564.98 |
| 44 | 435 | 3,942.37 | 3,387.57 | 30,168.12 | 646.08 | 180,569.45 | 40,370.68 | 229,354.89 |
| 45 | 442 | 1,105.15 | 1,024.25 | 15,539.30 | 377.75 | 79,137.01 | 17,200.53 | 99,759.74 |
| 46 | 453 | 2,653.06 | 1,154.31 | 28,714.81 | 458.42 | 54,671.95 | 34,687.61 | 95,752.28 |
| 47 | 465 | 3,467.53 | 1,228.44 | 104,793.48 | 449.80 | 49,598.92 | 115,491.30 | 170,751.85 |
| 48 | 475 | 3,804.78 | 1,011.30 | 79,629.55 | 612.72 | 147,125.54 | 90,030.34 | 242,957.51 |
| 49 | 481 | 4,009.00 | 1,042.04 | 24,095.28 | 444.93 | 202,258.89 | 33,571.90 | 241,873.42 |
| 50 | 488 | 4,086.36 | 1,133.51 | 64,958.38 | 606.19 | 120,182.31 | 74,024.54 | 200,472.29 |
| 51 | 495 | 3,887.23 | 1,152.12 | 25,650.44 | 549.59 | 104,379.88 | 34,888.61 | 145,355.38 |
| 52 | 506 | 3,771.02 | 1,283.21 | 36,248.18 | 426.09 | 105,737.86 | 46,070.19 | 157,932.30 |
| 53 | 515 | 3,770.34 | 1,359.40 | 27,293.44 | 457.59 | 77,735.42 | 36,481.43 | 120,425.35 |
| 54 | 530 | 4,125.37 | 1,185.02 | 29,543.77 | 586.81 | 79,206.30 | 39,837.38 | 125,430.33 |
| 55 | 538 | 3,973.49 | 3,475.44 | 19,478.28 | 654.11 | 70,817.53 | 29,064.18 | 108,458.95 |
| 56 | 553 | 4,113.62 | 1,047.00 | 151,400.82 | 920.60 | 65,733.51 | 161,457.08 | 233,519.73 |
| 57 | 562 | 4,038.64 | 1,142.00 | 481,378.65 | 588.35 | 187,414.79 | 491,092.72 | 684,825.82 |
| 58 | 571 | 3,928.67 | 1,117.73 | 29,860.66 | 1,776.29 | 649,580.20 | 41,382.24 | 697,225.62 |
| 59 | 582 | 3,974.58 | 1,098.45 | 65,003.41 | 640.82 | 529,534.27 | 74,320.17 | 610,098.29 |
| 60 | 589 | 4,057.11 | 1,251.51 | 58,819.61 | 509.75 | 112,520.12 | 68,496.47 | 187,567.90 |
| 61 | 596 | 3,972.92 | 1,077.25 | 81,917.41 | 897.34 | 139,952.23 | 92,020.13 | 238,256.37 |
| 62 | 607 | 3,982.55 | 1,206.68 | 64,204.37 | 536.33 | 157,593.46 | 73,671.72 | 237,719.90 |
| 63 | 615 | 4,324.93 | 1,209.12 | 24,763.52 | 472.20 | 162,488.61 | 34,758.46 | 204,008.34 |
| 64 | 625 | 4,250.86 | 1,107.42 | 38,803.08 | 655.19 | 105,346.56 | 48,924.86 | 160,931.85 |
| 65 | 634 | 4,086.91 | 1,093.11 | 22,440.62 | 500.58 | 80,799.75 | 32,309.75 | 119,545.33 |
| 66 | 642 | 3,993.74 | 1,699.06 | 68,471.99 | 519.27 | 77,859.61 | 78,559.76 | 163,410.97 |
| 67 | 649 | 3,926.67 | 1,260.56 | 28,353.57 | 774.98 | 108,009.80 | 38,603.93 | 153,098.11 |
| 68 | 658 | 4,059.60 | 1,093.95 | 24,599.99 | 512.75 | 114,387.41 | 34,062.68 | 154,937.20 |
| 69 | 664 | 4,331.09 | 1,041.53 | 26,298.89 | 458.99 | 69,723.54 | 35,762.89 | 112,262.71 |
| 70 | 671 | 4,068.49 | 1,293.86 | 26,664.12 | 398.33 | 67,015.82 | 36,283.07 | 110,131.57 |
| 71 | 678 | 4,079.50 | 1,039.75 | 20,652.23 | 581.00 | 69,606.77 | 30,045.66 | 106,182.21 |
| 72 | 686 | 4,099.11 | 6,292.55 | 24,061.21 | 421.44 | 58,622.15 | 33,560.96 | 103,972.73 |
| 73 | 695 | 4,199.24 | 1,056.71 | 23,358.63 | 505.25 | 60,971.63 | 33,343.48 | 101,010.85 |
| 74 | 708 | 4,038.81 | 999.93 | 22,079.09 | 648.70 | 64,527.27 | 32,986.60 | 104,129.60 |
| 75 | 720 | 4,372.25 | 833.77 | 171,998.97 | 549.29 | 63,956.62 | 180,452.82 | 251,020.03 |
| 76 | 725 | 1,208.21 | 496.17 | 8,326.01 | 489.71 | 214,216.56 | 9,229.41 | 226,906.42 |

The two latency columns on the right are unavailable for older serial records. Their original `end_to_end_memory_generation_ms` values remain in the raw audit; they are not silently mixed with pipeline admission-to-checkpoint measurements.

## Preprocessing and graph-update detail

| Segment | Deepgram | MAI | Speech embedding | Face detection | Face clustering | Graph update | ASR cache/precompute |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 472.55 | 986.02 | 1,027.02 | 3,793.50 | 5.53 | 0.33 | False/True |
| 2 | 782.73 | 1,803.30 | 1,257.93 | 4,098.13 | 5.47 | 5.41 | False/True |
| 3 | 860.50 | 1,041.90 | 307.50 | 2,383.97 | 2.38 | 2.42 | False/True |
| 4 | 940.46 | 1,593.54 | 394.19 | 2,598.44 | 6.90 | 10.03 | False/True |
| 5 | 258.09 | 540.95 | — | 2,357.20 | 0.07 | 0.08 | False/True |
| 6 | 2,209.94 | 1,949.03 | 178.39 | 2,660.12 | 5.41 | 4.70 | False/True |
| 7 | 803.01 | 999.66 | — | 2,268.32 | 3.00 | 0.07 | False/True |
| 8 | 437.32 | 809.33 | 682.85 | 2,661.58 | 7.07 | 8.98 | False/True |
| 9 | 354.70 | 949.26 | 376.40 | 3,037.95 | 7.32 | 8.60 | False/True |
| 10 | 812.18 | 3,395.97 | 578.95 | 2,789.03 | 6.92 | 16.86 | False/True |
| 11 | 1,890.61 | 808.89 | 349.03 | 2,488.47 | 4.25 | 9.48 | False/True |
| 12 | 1,069.61 | 870.85 | 181.15 | 2,588.16 | 4.37 | 7.60 | False/True |
| 13 | — | — | — | — | — | 6.81 | True/False |
| 14 | 2.72 | 2.59 | 2,010.64 | 4,157.41 | 8.29 | 22.00 | False/True |
| 15 | 321.46 | 1,365.68 | 105.24 | 1,535.36 | 0.65 | 7.07 | False/True |
| 16 | 439.82 | 3,053.57 | 327.47 | 871.69 | 1.05 | 9.02 | False/True |
| 17 | 1,054.75 | 1,111.01 | 439.66 | 2,891.57 | 6.87 | 14.75 | False/True |
| 18 | 439.47 | 954.58 | 611.91 | 2,877.27 | 3.54 | 20.62 | False/True |
| 19 | 938.26 | 989.35 | 990.05 | 3,053.27 | 10.18 | 36.22 | False/True |
| 20 | 265.00 | 960.21 | 507.85 | 3,011.87 | 8.26 | 16.79 | False/True |
| 21 | 364.12 | 968.63 | 979.93 | 3,079.63 | 8.64 | 44.77 | False/True |
| 22 | 255.44 | 1,154.18 | 1,345.19 | 3,278.21 | 13.92 | 50.67 | False/True |
| 23 | 1,721.89 | 1,249.80 | 868.36 | 3,226.76 | 9.73 | 49.93 | False/True |
| 24 | 1,241.85 | 3,501.69 | 697.27 | 3,256.37 | 7.14 | 43.66 | False/True |
| 25 | 1,384.78 | 3,018.71 | 451.52 | 1,599.38 | 6.69 | 20.22 | False/True |
| 26 | 651.36 | 759.32 | 339.68 | 1,222.99 | 2.72 | 23.82 | False/True |
| 27 | 823.50 | 1,222.53 | 340.75 | 3,269.25 | 5.90 | 20.99 | False/True |
| 28 | 883.01 | 818.59 | — | 2,449.57 | 0.36 | 0.10 | False/True |
| 29 | 1,348.28 | 962.34 | 906.83 | 3,199.55 | 7.28 | 44.82 | False/True |
| 30 | 978.96 | 570.09 | — | 2,525.93 | 0.17 | 0.23 | False/True |
| 31 | 880.74 | 3,200.55 | 395.48 | 3,087.94 | 16.39 | 34.40 | False/True |
| 32 | 1,036.19 | 1,000.79 | 557.24 | 3,432.62 | 9.51 | 33.13 | False/True |
| 33 | 893.83 | 964.44 | 1,102.02 | 3,306.52 | 7.97 | 58.35 | False/True |
| 34 | 438.80 | 2,253.98 | 487.85 | 3,332.47 | 7.09 | 27.39 | False/True |
| 35 | 900.01 | 1,262.93 | 672.01 | 3,213.39 | 6.88 | 41.06 | False/True |
| 36 | 961.83 | 1,133.07 | 956.12 | 3,352.68 | 12.40 | 57.71 | False/True |
| 37 | 917.80 | 964.16 | 883.59 | 3,300.26 | 8.62 | 68.83 | False/True |
| 38 | 525.49 | 1,049.24 | 1,100.61 | 3,644.74 | 6.96 | 79.28 | False/True |
| 39 | 890.02 | 1,069.49 | 690.90 | 3,134.25 | 7.83 | 55.18 | False/True |
| 40 | 903.73 | 1,032.39 | 1,121.59 | 3,394.72 | 9.94 | 71.50 | False/True |
| 41 | 1,102.99 | 996.97 | 891.55 | 3,155.68 | 18.60 | 59.79 | False/True |
| 42 | 928.68 | 969.05 | 1,354.99 | 3,294.28 | 8.21 | 90.94 | False/True |
| 43 | 502.02 | 1,069.39 | 678.46 | 3,073.70 | 7.48 | 45.02 | False/True |
| 44 | 438.28 | 3,386.67 | 769.04 | 3,338.47 | 7.20 | 121.22 | False/True |
| 45 | 175.97 | 1,022.93 | 209.38 | 577.43 | 2.12 | 23.31 | False/True |
| 46 | 537.61 | 1,153.27 | 420.72 | 2,266.90 | 5.18 | 40.34 | False/True |
| 47 | 250.08 | 1,227.52 | 1,434.72 | 3,375.50 | 9.43 | 127.53 | False/True |
| 48 | 866.73 | 1,010.34 | 792.29 | 3,303.82 | 27.80 | 70.39 | False/True |
| 49 | 854.96 | 1,041.14 | 765.68 | 3,036.36 | 21.69 | 66.77 | False/True |
| 50 | 1,035.89 | 1,132.52 | 482.01 | 3,033.27 | 7.34 | 50.50 | False/True |
| 51 | 390.02 | 1,151.12 | 463.60 | 3,213.02 | 7.08 | 36.35 | False/True |
| 52 | 234.85 | 1,282.23 | 1,152.89 | 3,107.95 | 6.55 | 103.58 | False/True |
| 53 | 908.64 | 1,357.86 | 341.58 | 3,249.96 | 7.64 | 46.58 | False/True |
| 54 | 291.85 | 1,184.30 | 1,218.87 | 3,367.44 | 9.76 | 110.12 | False/True |
| 55 | 777.65 | 3,474.50 | 637.91 | 3,475.03 | 10.31 | 88.74 | False/True |
| 56 | 558.46 | 1,046.15 | 584.05 | 3,634.22 | 31.35 | 94.54 | False/True |
| 57 | 1,138.02 | 1,103.06 | 808.44 | 3,217.94 | 20.81 | 76.09 | False/True |
| 58 | 242.64 | 1,116.66 | 903.13 | 3,304.60 | 20.86 | 80.31 | False/True |
| 59 | 289.20 | 1,088.74 | 289.13 | 3,183.76 | 31.84 | 47.65 | False/True |
| 60 | 807.95 | 1,250.65 | 478.13 | 3,435.63 | 6.86 | 45.72 | False/True |
| 61 | 303.66 | 1,075.67 | 658.28 | 3,259.01 | 6.94 | 70.98 | False/True |
| 62 | 482.26 | 1,205.73 | 398.50 | 3,363.67 | 7.16 | 64.99 | False/True |
| 63 | 976.99 | 1,207.92 | 867.04 | 3,382.74 | 11.20 | 80.83 | False/True |
| 64 | 1,106.38 | 1,000.33 | 601.52 | 3,504.69 | 24.56 | 62.82 | False/True |
| 65 | 338.40 | 1,091.96 | 686.03 | 3,312.68 | 8.91 | 65.30 | False/True |
| 66 | 288.38 | 1,698.21 | 638.23 | 3,529.26 | 7.61 | 64.04 | False/True |
| 67 | 926.38 | 1,259.34 | 860.97 | 3,256.26 | 6.91 | 114.36 | False/True |
| 68 | 984.32 | 1,092.52 | 572.38 | 3,011.09 | 5.36 | 78.45 | False/True |
| 69 | 350.71 | 1,040.21 | 309.71 | 3,471.92 | 9.17 | 39.74 | False/True |
| 70 | 703.11 | 1,292.45 | 451.14 | 3,452.71 | 7.45 | 57.59 | False/True |
| 71 | 276.98 | 1,038.30 | 390.21 | 3,291.10 | 8.49 | 57.83 | False/True |
| 72 | 6,291.59 | 860.45 | 181.83 | 3,399.56 | 7.27 | 37.72 | False/True |
| 73 | 812.64 | 1,055.54 | 902.14 | 3,268.52 | 6.85 | 128.85 | False/True |
| 74 | 262.84 | 998.64 | 1,201.28 | 3,263.82 | 7.11 | 211.17 | False/True |
| 75 | 792.35 | 832.43 | 64.00 | 2,380.72 | 5.27 | 22.64 | False/True |
| 76 | 495.40 | 335.31 | — | 207.61 | 0.13 | 0.06 | False/True |

ASR provider times can overlap; the ASR-stage column above is independently measured wall time. An ASR cache hit is not a new provider-speed measurement.

## Per-clip embedding batches

| Segment | Texts | Whole batch ms | Tokens | API attempts |
| --- | --- | --- | --- | --- |
| 1 | 9 | 697.44 | 149 | 1 |
| 2 | 8 | 1,765.58 | 126 | 1 |
| 3 | 9 | 417.62 | 130 | 1 |
| 4 | 9 | 507.32 | 167 | 1 |
| 5 | 8 | 505.58 | 136 | 1 |
| 6 | 9 | 376.44 | 166 | 1 |
| 7 | 8 | 475.54 | 149 | 1 |
| 8 | 10 | 490.52 | 147 | 1 |
| 9 | 7 | 665.32 | 100 | 1 |
| 10 | 9 | 528.15 | 151 | 1 |
| 11 | 10 | 391.60 | 182 | 1 |
| 12 | 11 | 638.42 | 184 | 1 |
| 13 | 9 | 625.05 | 106 | 1 |
| 14 | 9 | 631.79 | 130 | 1 |
| 15 | 8 | 500.32 | 109 | 1 |
| 16 | 8 | 556.80 | 163 | 1 |
| 17 | 10 | 706.02 | 241 | 1 |
| 18 | 12 | 606.95 | 218 | 1 |
| 19 | 8 | 653.14 | 158 | 1 |
| 20 | 10 | 488.42 | 178 | 1 |
| 21 | 8 | 739.42 | 190 | 1 |
| 22 | 9 | 466.76 | 173 | 1 |
| 23 | 11 | 530.15 | 201 | 1 |
| 24 | 10 | 500.39 | 237 | 1 |
| 25 | 8 | 405.61 | 130 | 1 |
| 26 | 11 | 726.39 | 186 | 1 |
| 27 | 9 | 555.08 | 158 | 1 |
| 28 | 12 | 498.90 | 205 | 1 |
| 29 | 12 | 600.42 | 206 | 1 |
| 30 | 7 | 428.48 | 121 | 1 |
| 31 | 9 | 1,154.54 | 195 | 1 |
| 32 | 10 | 478.60 | 165 | 1 |
| 33 | 8 | 551.56 | 166 | 1 |
| 34 | 9 | 527.06 | 219 | 1 |
| 35 | 10 | 540.40 | 220 | 1 |
| 36 | 8 | 802.28 | 151 | 1 |
| 37 | 10 | 428.58 | 170 | 1 |
| 38 | 9 | 539.14 | 146 | 1 |
| 39 | 8 | 499.04 | 145 | 1 |
| 40 | 8 | 534.39 | 132 | 1 |
| 41 | 8 | 544.57 | 142 | 1 |
| 42 | 9 | 605.91 | 179 | 1 |
| 43 | 8 | 487.37 | 135 | 1 |
| 44 | 11 | 646.08 | 170 | 1 |
| 45 | 7 | 377.75 | 120 | 1 |
| 46 | 10 | 458.42 | 171 | 1 |
| 47 | 9 | 449.80 | 152 | 1 |
| 48 | 10 | 612.72 | 168 | 1 |
| 49 | 6 | 444.93 | 111 | 1 |
| 50 | 7 | 606.19 | 157 | 1 |
| 51 | 7 | 549.59 | 136 | 1 |
| 52 | 10 | 426.09 | 156 | 1 |
| 53 | 9 | 457.59 | 198 | 1 |
| 54 | 13 | 586.81 | 225 | 1 |
| 55 | 10 | 654.11 | 156 | 1 |
| 56 | 13 | 920.60 | 277 | 1 |
| 57 | 8 | 588.35 | 142 | 1 |
| 58 | 9 | 1,776.29 | 185 | 1 |
| 59 | 11 | 640.82 | 191 | 1 |
| 60 | 7 | 509.75 | 117 | 1 |
| 61 | 7 | 897.34 | 111 | 1 |
| 62 | 10 | 536.33 | 180 | 1 |
| 63 | 7 | 472.20 | 128 | 1 |
| 64 | 9 | 655.19 | 179 | 1 |
| 65 | 8 | 500.58 | 136 | 1 |
| 66 | 8 | 519.27 | 122 | 1 |
| 67 | 7 | 774.98 | 152 | 1 |
| 68 | 9 | 512.75 | 142 | 1 |
| 69 | 6 | 458.99 | 108 | 1 |
| 70 | 7 | 398.33 | 119 | 1 |
| 71 | 8 | 581.00 | 150 | 1 |
| 72 | 8 | 421.44 | 164 | 1 |
| 73 | 9 | 505.25 | 164 | 1 |
| 74 | 9 | 648.70 | 177 | 1 |
| 75 | 12 | 549.29 | 260 | 1 |
| 76 | 5 | 489.71 | 83 | 1 |

Each input retains its own vector. Individual-text latency is unavailable; batch time is not divided by text count.

## Timing-policy boundaries

| First segment | ASR | HTTP | Embedding | Lookahead |
| --- | --- | --- | --- | --- |
| 1 | concurrent Deepgram and MAI | pooled connections | whole-clip batch | 2 |

## QA measurements

| Q | Method | Mode | Retrieval requests | Reasoning calls | Retrieval total | Reasoning total | Question → answer | Answer | Correct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | A | warm_retrieval_uncached_question | 4 | 6 | 1,226.49 | 37,656.28 | 38,885.27 | Taller one | True |
| 2 | A | warm_retrieval_uncached_question | 1 | 2 | 386.16 | 10,126.09 | 10,513.20 | No, Emma's tidying up habit is not good. | True |
| 3 | A | warm_retrieval_uncached_question | 2 | 3 | 998.18 | 17,862.88 | 18,862.45 | Emma’s mother places heavy stress and high expectations on Emma’s academic performance and grades. | True |
| 4 | A | warm_retrieval_uncached_question | 4 | 6 | 2,599.83 | 98,886.45 | 101,489.33 | Creativity (creative ability) | False |
| 5 | A | warm_retrieval_uncached_question | 1 | 2 | 327.42 | 14,302.04 | 14,630.35 | ** Emma plans to improve her programming skills by working on hands-on programming projects and participating in programming competitions. | False |
| 6 | A | warm_retrieval_uncached_question | 1 | 2 | 359.63 | 9,022.44 | 9,382.94 | Lily likes mocha. | True |
| 7 | A | warm_retrieval_uncached_question | 4 | 6 | 1,495.42 | 28,181.83 | 29,680.47 | Computer Science | True |
| 8 | A | warm_retrieval_uncached_question | 4 | 6 | 1,314.78 | 85,319.93 | 86,637.40 | shorter one | True |
| 9 | A | warm_retrieval_uncached_question | 4 | 6 | 1,465.06 | 91,401.48 | 92,868.95 | 4:00 PM | True |
| 10 | A | warm_retrieval_uncached_question | 4 | 6 | 1,335.97 | 40,338.82 | 41,677.45 | McDonald's fries, a slice of cake, bread slices, and coffee. | False |
| 11 | A | warm_retrieval_uncached_question | 4 | 5 | 1,487.90 | 31,558.95 | 33,049.25 | Emma's afternoon tea consists of french fries, cake, and coffee. | False |
| 12 | A | warm_retrieval_uncached_question | 1 | 2 | 374.90 | 11,334.60 | 11,710.39 | Lily was supportive, understanding, and reassuring toward Emma, offering comfort and encouragement rather than being critical. | False |
| 13 | A | warm_retrieval_uncached_question | 4 | 6 | 1,941.30 | 42,797.40 | 44,741.69 | No, Emma's allergy is not serious. | True |
| 14 | A | warm_retrieval_uncached_question | 1 | 2 | 527.71 | 12,564.23 | 13,092.81 | Designer | True |
| 15 | A | warm_retrieval_uncached_question | 4 | 6 | 1,615.57 | 86,782.50 | 88,401.02 | Yes, Lily likes her job. | True |
| 1 | B | warm_retrieval_uncached_question | 1 | 1 | 336.90 | 5,896.27 | 6,234.06 | The retrieved memories are insufficient to answer this question. | False |
| 2 | B | warm_retrieval_uncached_question | 1 | 1 | 365.13 | 5,805.13 | 6,170.77 | No. The memories indicate her tidying habit is not good, as someone is frustrated by a cluttered desk and suspects Emma caused it. | True |
| 3 | B | warm_retrieval_uncached_question | 1 | 1 | 406.58 | 88,761.82 | 89,168.91 | Emma’s mother stresses heavily over her academic performance. | False |
| 4 | B | warm_retrieval_uncached_question | 1 | 1 | 394.37 | 5,133.45 | 5,528.39 | The retrieved memories are insufficient to answer this question. | False |
| 5 | B | warm_retrieval_uncached_question | 1 | 1 | 457.04 | 8,573.05 | 9,030.76 | Emma plans to work on programming projects, share her first successful project, and participate in programming competitions. | False |
| 6 | B | warm_retrieval_uncached_question | 1 | 1 | 387.23 | 9,378.20 | 9,766.11 | Based on the retrieved memories, the information is insufficient to determine what kind of coffee Lily likes. | False |
| 7 | B | warm_retrieval_uncached_question | 1 | 1 | 366.44 | 8,663.78 | 9,030.83 | The retrieved memories do not specify Emma's major, though they mention her interest and background in coding and computer science. Therefore, the memories are insufficient to give a definitive answer. | False |
| 8 | B | warm_retrieval_uncached_question | 1 | 1 | 372.83 | 5,144.88 | 5,518.37 | The retrieved memories are insufficient to answer this question, as they do not mention whether the coat rack is the taller or shorter one. | False |
| 9 | B | warm_retrieval_uncached_question | 1 | 1 | 263.23 | 2,576.10 | 2,839.77 | The retrieved memories are insufficient to answer when Lily originally needs afternoon tea. | False |
| 10 | B | warm_retrieval_uncached_question | 1 | 1 | 431.95 | 6,094.67 | 6,527.18 | Based on the retrieved memories, "Lily" is not mentioned, so the memories are insufficient to answer what is included in her afternoon tea. | False |
| 11 | B | warm_retrieval_uncached_question | 1 | 1 | 733.53 | 5,820.45 | 6,554.55 | Based on the retrieved memories, the afternoon tea served at the table consists of a slice of cake, snacks, and a drink in a mug (with available afternoon tea items noted as coffee, fries, and cakes). | False |
| 12 | B | warm_retrieval_uncached_question | 1 | 1 | 313.99 | 4,058.45 | 4,372.94 | Lily had a supportive and reassuring attitude; she offered Emma comfort and encouragement, reassuring her that failing an exam is not the end of the world. | False |
| 13 | B | warm_retrieval_uncached_question | 1 | 1 | 382.52 | 3,637.11 | 4,020.20 | Based on the retrieved memories, the information is insufficient to determine if Emma's allergy is serious. (The memories only mention an inquiry about the severity of her allergic reaction during an exam, but do not state the answer.) | False |
| 14 | B | warm_retrieval_uncached_question | 1 | 1 | 478.70 | 2,785.20 | 3,264.42 | Lily is a designer. | True |
| 15 | B | warm_retrieval_uncached_question | 1 | 1 | 385.71 | 5,547.06 | 5,933.39 | Yes. Although she finds it exhausting and stressful due to deadlines, Lily remains passionate about her work, deeply appreciates the creative process, and takes pride in completing her design work. | True |
| 1 | C | warm_retrieval_uncached_question | 1 | 1 | 279.83 | 5,060.87 | 5,341.33 | The retrieved memories are insufficient to determine whether Emma's coat should be placed on the taller or shorter coat rack. | False |
| 2 | C | warm_retrieval_uncached_question | 1 | 1 | 391.84 | 5,602.37 | 5,994.74 | No, Emma's tidying up habit does not appear to be good; another woman is frustrated by the cluttered condition of a desk and suspects Emma caused it. | True |
| 3 | C | warm_retrieval_uncached_question | 1 | 1 | 328.76 | 16,441.76 | 16,771.18 | Emma’s mother stresses heavily over her academic performance. | False |
| 4 | C | warm_retrieval_uncached_question | 1 | 1 | 320.49 | 15,350.00 | 15,671.84 | Based on the retrieved memories, the information is insufficient to answer what Lily thinks is the most important ability of a designer. | False |
| 5 | C | warm_retrieval_uncached_question | 1 | 1 | 371.79 | 6,575.33 | 6,947.68 | Based on the retrieved memories, Emma plans to work on programming projects, share her first successful project, and participate in programming competitions. | False |
| 6 | C | warm_retrieval_uncached_question | 1 | 1 | 295.55 | 10,552.04 | 10,848.07 | Based on the retrieved memories, Lily likes mocha (she orders a mocha). | True |
| 7 | C | warm_retrieval_uncached_question | 1 | 1 | 733.90 | 5,254.33 | 5,988.73 | The retrieved memories are insufficient to determine Emma's major. | False |
| 8 | C | warm_retrieval_uncached_question | 1 | 1 | 238.74 | 3,949.87 | 4,189.09 | Based on the retrieved memories, the information is insufficient to determine whether Emma's hat should be placed on the taller or shorter coat rack. | False |
| 9 | C | warm_retrieval_uncached_question | 1 | 1 | 350.49 | 3,097.17 | 3,448.16 | Based on the retrieved memories, the information is insufficient to answer when Lily originally needs afternoon tea. | False |
| 10 | C | warm_retrieval_uncached_question | 1 | 1 | 235.27 | 3,761.68 | 3,997.45 | The retrieved memories are insufficient to answer the question, as Lily is not mentioned. | False |
| 11 | C | warm_retrieval_uncached_question | 1 | 1 | 288.56 | 6,566.88 | 6,855.92 | The retrieved memories are insufficient to determine specifically what Emma's afternoon tea is. (The memories only note that available afternoon tea items include coffee, fries, and cakes, and that snacks, a cake slice, a mug, and bottles were on the table). | False |
| 12 | C | warm_retrieval_uncached_question | 1 | 1 | 1,963.13 | 4,410.44 | 6,374.12 | Lily had a reassuring and supportive attitude, comforting Emma and reassuring her that failing an exam is not the end of the world. | False |
| 13 | C | warm_retrieval_uncached_question | 1 | 1 | 312.52 | 4,070.54 | 4,383.61 | Based on the retrieved memories, the information is insufficient to determine whether Emma's allergy is serious. (The memories only mention that she ate an allergen and that someone inquired about the severity of her allergic reaction, but they do not state the severity.) | False |
| 14 | C | warm_retrieval_uncached_question | 1 | 1 | 524.77 | 5,051.95 | 5,577.24 | The retrieved memories are insufficient to determine Lily's occupation. | False |
| 15 | C | warm_retrieval_uncached_question | 1 | 1 | 427.54 | 5,333.12 | 5,761.15 | Yes, Lily remains passionate and energetic about her work despite it being exhausting. | True |
| 1 | D | warm_retrieval_uncached_question | 1 | 1 | 2,413.63 | 9,166.50 | 11,581.03 | Based on the retrieved memories, there is insufficient information to determine whether Emma's coat should be placed on the taller or shorter coat rack. | False |
| 2 | D | warm_retrieval_uncached_question | 1 | 1 | 2,387.26 | 3,511.50 | 5,899.72 | Based on the retrieved memories, no, Emma’s tidying up habit does not seem good; another woman was frustrated by a cluttered desk suspected to have been caused by Emma and had to remind her to throw something into the bin. | True |
| 3 | D | warm_retrieval_uncached_question | 1 | 1 | 2,381.73 | 5,372.50 | 7,755.85 | Emma’s mother places high pressure and expectations on her academic studies, stressing heavily over her academic performance. | True |
| 4 | D | warm_retrieval_uncached_question | 1 | 1 | 2,372.81 | 9,658.28 | 12,033.16 | Based on the retrieved memories, the information is insufficient to answer what Lily thinks is the most important ability of a designer. | False |
| 5 | D | warm_retrieval_uncached_question | 1 | 1 | 2,255.99 | 7,304.80 | 9,562.34 | Emma plans to improve her programming skills by sharing her first successful project and participating in programming/technical competitions. | False |
| 6 | D | warm_retrieval_uncached_question | 1 | 1 | 2,278.12 | 6,155.79 | 8,435.46 | Based on the retrieved memories, Lily likes mocha (she orders a mocha). | True |
| 7 | D | warm_retrieval_uncached_question | 1 | 1 | 2,310.28 | 3,698.76 | 6,010.06 | The retrieved memories are insufficient to determine Emma's major. | False |
| 8 | D | warm_retrieval_uncached_question | 1 | 1 | 2,439.31 | 6,102.57 | 8,542.89 | Based on the retrieved memories, there is insufficient information to determine whether Emma's hat should be placed on the taller or shorter coat rack. | False |
| 9 | D | warm_retrieval_uncached_question | 1 | 1 | 1,498.71 | 7,072.69 | 8,572.18 | The retrieved memories are insufficient to answer this question. | False |
| 10 | D | warm_retrieval_uncached_question | 1 | 1 | 3,768.27 | 13,699.84 | 17,470.27 | While Lily is not mentioned by name, the afternoon tea ordered and prepared in the memories includes:<br><br>* **Coffee** (specifically a mocha)<br>* **Fries** (with ketchup)<br>* **Strawberry cake**<br>* **Bread slices** <br><br>*(Note: If "Lily" refers to someone else, the memories are insufficient to identify her.)* | False |
| 11 | D | warm_retrieval_uncached_question | 1 | 1 | 2,285.31 | 13,180.98 | 15,467.48 | The retrieved memories are insufficient to specify what Emma's afternoon tea is (though available afternoon tea items listed include coffee, fries, and cakes). | False |
| 12 | D | warm_retrieval_uncached_question | 1 | 1 | 2,436.74 | 4,930.32 | 7,369.23 | Lily was supportive, empathetic, and reassuring, offering comfort, patience, and emotional support to help soothe Emma. | False |
| 13 | D | warm_retrieval_uncached_question | 1 | 1 | 2,442.83 | 29,819.87 | 32,263.81 | The provided memories are insufficient to determine whether Emma's allergy is serious; they only note that she had an allergic reaction to strawberries during an exam and did not anticipate the severity of the reaction. | False |
| 14 | D | warm_retrieval_uncached_question | 1 | 1 | 2,458.64 | 7,696.03 | 10,156.65 | The retrieved memories are insufficient to determine Lily's occupation. | False |
| 15 | D | warm_retrieval_uncached_question | 1 | 1 | 2,519.95 | 6,230.14 | 8,752.10 | Yes, she remains passionate and energetic about her work, though she acknowledges it can be exhausting, stressful, and difficult. | True |

### Retrieval-stage detail

| Q/method/round | Embedding | Dense | Sparse | StreamMeCo scoring | Fusion | Lookup | Rerank | Total |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1/A/1 | 255.04 | 17.22 | 0.00 | 0.10 | — | 0.34 | 0.00 | 273.06 |
| 1/A/2 | 232.88 | 15.82 | 0.00 | 0.11 | — | 0.05 | 0.00 | 249.17 |
| 1/A/3 | 286.05 | 17.32 | 0.00 | 0.10 | — | 0.04 | 0.00 | 303.82 |
| 1/A/4 | 383.86 | 16.08 | 0.00 | 0.11 | — | 0.04 | 0.00 | 400.43 |
| 2/A/1 | 305.15 | 78.86 | 0.00 | 0.65 | — | 0.92 | 0.00 | 386.16 |
| 3/A/1 | 323.07 | 97.13 | 0.00 | 0.68 | — | 0.96 | 0.00 | 422.44 |
| 3/A/2 | 498.70 | 74.94 | 0.00 | 0.68 | — | 0.83 | 0.00 | 575.74 |
| 4/A/1 | 1,476.62 | 79.44 | 0.00 | 0.67 | — | 0.96 | 0.00 | 1,558.28 |
| 4/A/2 | 306.87 | 9.34 | 0.00 | 0.08 | — | 0.26 | 0.00 | 316.87 |
| 4/A/3 | 270.09 | 81.63 | 0.00 | 0.67 | — | 0.70 | 0.00 | 353.71 |
| 4/A/4 | 288.81 | 79.78 | 0.00 | 1.00 | — | 0.66 | 0.00 | 370.97 |
| 5/A/1 | 245.53 | 79.38 | 0.00 | 0.91 | — | 0.99 | 0.00 | 327.42 |
| 6/A/1 | 278.20 | 79.22 | 0.00 | 0.69 | — | 0.94 | 0.00 | 359.63 |
| 7/A/1 | 341.67 | 79.80 | 0.00 | 0.90 | — | 0.93 | 0.00 | 423.92 |
| 7/A/2 | 267.43 | 89.54 | 0.00 | 0.70 | — | 0.82 | 0.00 | 359.12 |
| 7/A/3 | 323.30 | 80.59 | 0.00 | 0.72 | — | 0.73 | 0.00 | 405.99 |
| 7/A/4 | 227.56 | 76.95 | 0.00 | 0.68 | — | 0.56 | 0.00 | 306.39 |
| 8/A/1 | 286.12 | 17.44 | 0.00 | 0.13 | — | 0.32 | 0.00 | 304.34 |
| 8/A/2 | 306.04 | 17.53 | 0.00 | 0.12 | — | 0.04 | 0.00 | 324.09 |
| 8/A/3 | 318.65 | 18.67 | 0.00 | 0.11 | — | 0.04 | 0.00 | 337.85 |
| 8/A/4 | 330.07 | 17.93 | 0.00 | 0.13 | — | 0.04 | 0.00 | 348.50 |
| 9/A/1 | 270.73 | 4.34 | 0.00 | 0.02 | — | 0.15 | 0.00 | 275.48 |
| 9/A/2 | 253.20 | 4.18 | 0.00 | 0.02 | — | 0.01 | 0.00 | 257.63 |
| 9/A/3 | 609.14 | 4.31 | 0.00 | 0.02 | — | 0.03 | 0.00 | 613.69 |
| 9/A/4 | 312.44 | 5.57 | 0.00 | 0.03 | — | 0.01 | 0.00 | 318.26 |
| 10/A/1 | 247.04 | 27.89 | 0.00 | 0.26 | — | 0.49 | 0.00 | 276.08 |
| 10/A/2 | 364.50 | 30.18 | 0.00 | 0.26 | — | 0.32 | 0.00 | 395.68 |
| 10/A/3 | 227.45 | 28.09 | 0.00 | 0.21 | — | 0.06 | 0.00 | 256.18 |
| 10/A/4 | 378.51 | 28.84 | 0.00 | 0.23 | — | 0.08 | 0.00 | 408.03 |
| 11/A/1 | 363.61 | 51.28 | 0.00 | 0.54 | — | 0.61 | 0.00 | 416.52 |
| 11/A/2 | 301.33 | 52.55 | 0.00 | 0.38 | — | 0.53 | 0.00 | 355.29 |
| 11/A/3 | 239.87 | 51.37 | 0.00 | 0.40 | — | 0.34 | 0.00 | 292.49 |
| 11/A/4 | 370.84 | 51.67 | 0.00 | 0.43 | — | 0.14 | 0.00 | 423.61 |
| 12/A/1 | 291.13 | 81.47 | 0.00 | 0.67 | — | 1.02 | 0.00 | 374.90 |
| 13/A/1 | 264.95 | 80.06 | 0.00 | 0.75 | — | 0.93 | 0.00 | 347.29 |
| 13/A/2 | 352.32 | 81.28 | 0.00 | 0.87 | — | 0.83 | 0.00 | 435.92 |
| 13/A/3 | 605.60 | 82.72 | 0.00 | 0.67 | — | 0.65 | 0.00 | 690.25 |
| 13/A/4 | 341.70 | 124.21 | 0.00 | 0.69 | — | 0.62 | 0.00 | 467.84 |
| 14/A/1 | 444.81 | 80.47 | 0.00 | 0.86 | — | 0.94 | 0.00 | 527.71 |
| 15/A/1 | 299.55 | 79.82 | 0.00 | 0.68 | — | 0.95 | 0.00 | 381.59 |
| 15/A/2 | 364.65 | 80.48 | 0.00 | 0.74 | — | 0.84 | 0.00 | 447.41 |
| 15/A/3 | 221.38 | 80.63 | 0.00 | 0.86 | — | 0.68 | 0.00 | 304.19 |
| 15/A/4 | 399.56 | 80.77 | 0.00 | 0.86 | — | 0.53 | 0.00 | 482.38 |
| 1/B/1 | 295.60 | 40.15 | 0.00 | 0.24 | — | 0.42 | 0.00 | 336.90 |
| 2/B/1 | 278.03 | 82.36 | 0.00 | 0.63 | — | 3.53 | 0.00 | 365.13 |
| 3/B/1 | 325.60 | 78.67 | 0.00 | 0.72 | — | 0.96 | 0.00 | 406.58 |
| 4/B/1 | 308.94 | 83.16 | 0.00 | 0.70 | — | 0.95 | 0.00 | 394.37 |
| 5/B/1 | 354.02 | 100.39 | 0.00 | 0.91 | — | 1.04 | 0.00 | 457.04 |
| 6/B/1 | 289.55 | 95.14 | 0.00 | 0.80 | — | 0.98 | 0.00 | 387.23 |
| 7/B/1 | 280.03 | 83.90 | 0.00 | 0.97 | — | 0.94 | 0.00 | 366.44 |
| 8/B/1 | 353.34 | 18.54 | 0.00 | 0.19 | — | 0.35 | 0.00 | 372.83 |
| 9/B/1 | 258.78 | 4.19 | 0.00 | 0.02 | — | 0.12 | 0.00 | 263.23 |
| 10/B/1 | 401.55 | 29.07 | 0.00 | 0.33 | — | 0.51 | 0.00 | 431.95 |
| 11/B/1 | 638.91 | 92.80 | 0.00 | 0.49 | — | 0.77 | 0.00 | 733.53 |
| 12/B/1 | 227.77 | 83.91 | 0.00 | 0.77 | — | 0.92 | 0.00 | 313.99 |
| 13/B/1 | 295.24 | 84.89 | 0.00 | 0.82 | — | 0.93 | 0.00 | 382.52 |
| 14/B/1 | 387.77 | 88.43 | 0.00 | 0.85 | — | 0.94 | 0.00 | 478.70 |
| 15/B/1 | 299.89 | 83.53 | 0.00 | 0.70 | — | 1.00 | 0.00 | 385.71 |
| 1/C/1 | 265.82 | 13.23 | 0.00 | 0.10 | — | 0.34 | 0.00 | 279.83 |
| 2/C/1 | 329.50 | 60.28 | 0.00 | 0.64 | — | 0.87 | 0.00 | 391.84 |
| 3/C/1 | 256.89 | 69.67 | 0.00 | 0.77 | — | 0.85 | 0.00 | 328.76 |
| 4/C/1 | 246.55 | 70.60 | 0.00 | 0.77 | — | 0.92 | 0.00 | 320.49 |
| 5/C/1 | 305.78 | 63.97 | 0.00 | 0.63 | — | 0.88 | 0.00 | 371.79 |
| 6/C/1 | 219.26 | 74.15 | 0.00 | 0.68 | — | 0.87 | 0.00 | 295.55 |
| 7/C/1 | 659.15 | 72.64 | 0.00 | 0.68 | — | 0.84 | 0.00 | 733.90 |
| 8/C/1 | 221.69 | 16.15 | 0.00 | 0.10 | — | 0.47 | 0.00 | 238.74 |
| 9/C/1 | 346.10 | 3.97 | 0.00 | 0.02 | — | 0.18 | 0.00 | 350.49 |
| 10/C/1 | 212.16 | 22.11 | 0.00 | 0.20 | — | 0.41 | 0.00 | 235.27 |
| 11/C/1 | 243.26 | 43.69 | 0.00 | 0.44 | — | 0.61 | 0.00 | 288.56 |
| 12/C/1 | 1,897.64 | 63.23 | 0.00 | 0.71 | — | 0.96 | 0.00 | 1,963.13 |
| 13/C/1 | 245.09 | 65.28 | 0.00 | 0.68 | — | 0.87 | 0.00 | 312.52 |
| 14/C/1 | 459.92 | 62.78 | 0.00 | 0.62 | — | 0.88 | 0.00 | 524.77 |
| 15/C/1 | 359.07 | 66.32 | 0.00 | 0.67 | — | 0.87 | 0.00 | 427.54 |
| 1/D/1 | 751.17 | 8.09 | 28.72 | 0.00 | 0.31 | 0.44 | 1,646.90 | 2,413.63 |
| 2/D/1 | 640.62 | 5.92 | 17.64 | 0.00 | 0.53 | 1.01 | 1,731.34 | 2,387.26 |
| 3/D/1 | 740.65 | 7.94 | 19.23 | 0.00 | 0.70 | 1.00 | 1,624.47 | 2,381.73 |
| 4/D/1 | 744.11 | 6.06 | 20.28 | 0.00 | 0.45 | 1.10 | 1,615.80 | 2,372.81 |
| 5/D/1 | 636.60 | 3.69 | 24.39 | 0.00 | 0.52 | 1.30 | 1,607.89 | 2,255.99 |
| 6/D/1 | 617.56 | 6.03 | 17.93 | 0.00 | 0.44 | 1.04 | 1,647.92 | 2,278.12 |
| 7/D/1 | 661.43 | 5.84 | 19.74 | 0.00 | 0.47 | 1.31 | 1,635.86 | 2,310.28 |
| 8/D/1 | 783.85 | 4.87 | 20.28 | 0.00 | 0.32 | 0.42 | 1,642.86 | 2,439.31 |
| 9/D/1 | 631.89 | 4.01 | 18.75 | 0.00 | 0.15 | 0.09 | 860.24 | 1,498.71 |
| 10/D/1 | 746.65 | 2.63 | 19.73 | 0.00 | 0.37 | 1.23 | 3,010.97 | 3,768.27 |
| 11/D/1 | 684.46 | 3.26 | 23.69 | 0.00 | 0.55 | 0.98 | 1,591.74 | 2,285.31 |
| 12/D/1 | 720.70 | 7.52 | 20.17 | 0.00 | 0.96 | 1.14 | 1,694.71 | 2,436.74 |
| 13/D/1 | 721.09 | 5.34 | 19.48 | 0.00 | 0.42 | 1.03 | 1,709.76 | 2,442.83 |
| 14/D/1 | 811.42 | 5.60 | 18.70 | 0.00 | 0.60 | 1.07 | 1,631.18 | 2,458.64 |
| 15/D/1 | 799.67 | 8.18 | 18.69 | 0.00 | 0.97 | 1.16 | 1,699.04 | 2,519.95 |

### Reasoning calls

| Q/method/call | Purpose | Latency | Input tokens | Output tokens |
| --- | --- | --- | --- | --- |
| 1/A/1 | controller | 3,606.31 | 1246 | 169 |
| 1/A/2 | controller | 4,799.85 | 1752 | 444 |
| 1/A/3 | controller | 8,150.29 | 1808 | 920 |
| 1/A/4 | controller | 7,950.73 | 1997 | 912 |
| 1/A/5 | controller | 7,906.82 | 2153 | 1903 |
| 1/A/6 | forced_final_answer | 5,242.29 | 1282 | 1058 |
| 2/A/1 | controller | 4,417.12 | 1239 | 277 |
| 2/A/2 | controller | 5,708.97 | 1843 | 715 |
| 3/A/1 | controller | 3,338.13 | 1244 | 198 |
| 3/A/2 | controller | 9,059.40 | 1849 | 931 |
| 3/A/3 | controller | 5,465.34 | 2550 | 468 |
| 4/A/1 | controller | 3,234.34 | 1242 | 204 |
| 4/A/2 | controller | 7,849.70 | 1857 | 584 |
| 4/A/3 | controller | 40,588.50 | 2529 | 5454 |
| 4/A/4 | controller | 8,850.02 | 3157 | 885 |
| 4/A/5 | controller | 23,359.84 | 3771 | 6011 |
| 4/A/6 | forced_final_answer | 15,004.06 | 2856 | 1779 |
| 5/A/1 | controller | 3,447.66 | 1239 | 237 |
| 5/A/2 | controller | 10,854.38 | 1851 | 1488 |
| 6/A/1 | controller | 3,510.82 | 1237 | 156 |
| 6/A/2 | controller | 5,511.61 | 1798 | 1158 |
| 7/A/1 | controller | 5,225.30 | 1236 | 231 |
| 7/A/2 | controller | 4,905.23 | 1788 | 568 |
| 7/A/3 | controller | 3,549.93 | 2393 | 391 |
| 7/A/4 | controller | 5,281.54 | 3091 | 314 |
| 7/A/5 | controller | 5,789.93 | 3628 | 613 |
| 7/A/6 | forced_final_answer | 3,429.89 | 2714 | 226 |
| 8/A/1 | controller | 3,641.05 | 1246 | 226 |
| 8/A/2 | controller | 5,613.73 | 1793 | 366 |
| 8/A/3 | controller | 22,381.61 | 1850 | 3077 |
| 8/A/4 | controller | 18,612.91 | 2026 | 2315 |
| 8/A/5 | controller | 21,648.19 | 2216 | 3039 |
| 8/A/6 | forced_final_answer | 13,422.44 | 1345 | 1355 |
| 9/A/1 | controller | 3,178.27 | 1237 | 141 |
| 9/A/2 | controller | 4,916.66 | 1630 | 484 |
| 9/A/3 | controller | 12,067.85 | 1667 | 1435 |
| 9/A/4 | controller | 25,894.00 | 1847 | 3277 |
| 9/A/5 | controller | 37,113.90 | 2070 | 5437 |
| 9/A/6 | forced_final_answer | 8,230.80 | 1199 | 791 |
| 10/A/1 | controller | 3,523.77 | 1239 | 200 |
| 10/A/2 | controller | 5,980.46 | 1809 | 407 |
| 10/A/3 | controller | 5,476.05 | 2385 | 478 |
| 10/A/4 | controller | 8,131.24 | 2477 | 874 |
| 10/A/5 | controller | 12,359.81 | 2642 | 1039 |
| 10/A/6 | forced_final_answer | 4,867.50 | 1771 | 475 |
| 11/A/1 | controller | 3,702.75 | 1238 | 148 |
| 11/A/2 | controller | 5,556.24 | 1789 | 504 |
| 11/A/3 | controller | 4,484.44 | 2504 | 419 |
| 11/A/4 | controller | 6,741.59 | 3040 | 692 |
| 11/A/5 | controller | 11,073.92 | 3103 | 1538 |
| 12/A/1 | controller | 3,991.64 | 1241 | 263 |
| 12/A/2 | controller | 7,342.96 | 1826 | 678 |
| 13/A/1 | controller | 3,581.06 | 1236 | 196 |
| 13/A/2 | controller | 6,528.55 | 1802 | 347 |
| 13/A/3 | controller | 4,691.41 | 2440 | 456 |
| 13/A/4 | controller | 5,151.23 | 3057 | 373 |
| 13/A/5 | controller | 10,504.97 | 3643 | 1192 |
| 13/A/6 | forced_final_answer | 12,340.18 | 2729 | 1425 |
| 14/A/1 | controller | 3,838.49 | 1236 | 172 |
| 14/A/2 | controller | 8,725.74 | 1828 | 1080 |
| 15/A/1 | controller | 3,157.94 | 1235 | 184 |
| 15/A/2 | controller | 60,818.11 | 1825 | 587 |
| 15/A/3 | controller | 4,342.78 | 2541 | 396 |
| 15/A/4 | controller | 5,192.88 | 3229 | 386 |
| 15/A/5 | controller | 6,844.35 | 3851 | 453 |
| 15/A/6 | forced_final_answer | 6,426.43 | 2937 | 646 |
| 1/B/1 | final_answer | 5,896.27 | 511 | 422 |
| 2/B/1 | final_answer | 5,805.13 | 565 | 561 |
| 3/B/1 | final_answer | 88,761.82 | 566 | 289 |
| 4/B/1 | final_answer | 5,133.45 | 567 | 512 |
| 5/B/1 | final_answer | 8,573.05 | 550 | 1129 |
| 6/B/1 | final_answer | 9,378.20 | 509 | 701 |
| 7/B/1 | final_answer | 8,663.78 | 532 | 889 |
| 8/B/1 | final_answer | 5,144.88 | 503 | 497 |
| 9/B/1 | final_answer | 2,576.10 | 373 | 285 |
| 10/B/1 | final_answer | 6,094.67 | 553 | 553 |
| 11/B/1 | final_answer | 5,820.45 | 524 | 759 |
| 12/B/1 | final_answer | 4,058.45 | 562 | 367 |
| 13/B/1 | final_answer | 3,637.11 | 531 | 299 |
| 14/B/1 | final_answer | 2,785.20 | 545 | 355 |
| 15/B/1 | final_answer | 5,547.06 | 561 | 409 |
| 1/C/1 | final_answer | 5,060.87 | 513 | 457 |
| 2/C/1 | final_answer | 5,602.37 | 548 | 572 |
| 3/C/1 | final_answer | 16,441.76 | 557 | 281 |
| 4/C/1 | final_answer | 15,350.00 | 565 | 160 |
| 5/C/1 | final_answer | 6,575.33 | 551 | 545 |
| 6/C/1 | final_answer | 10,552.04 | 544 | 337 |
| 7/C/1 | final_answer | 5,254.33 | 525 | 602 |
| 8/C/1 | final_answer | 3,949.87 | 516 | 180 |
| 9/C/1 | final_answer | 3,097.17 | 386 | 318 |
| 10/C/1 | final_answer | 3,761.68 | 547 | 759 |
| 11/C/1 | final_answer | 6,566.88 | 513 | 771 |
| 12/C/1 | final_answer | 4,410.44 | 551 | 383 |
| 13/C/1 | final_answer | 4,070.54 | 548 | 350 |
| 14/C/1 | final_answer | 5,051.95 | 571 | 434 |
| 15/C/1 | final_answer | 5,333.12 | 569 | 366 |
| 1/D/1 | final_answer | 9,166.50 | 8170 | 252 |
| 2/D/1 | final_answer | 3,511.50 | 8248 | 271 |
| 3/D/1 | final_answer | 5,372.50 | 8269 | 183 |
| 4/D/1 | final_answer | 9,658.28 | 8387 | 349 |
| 5/D/1 | final_answer | 7,304.80 | 8312 | 522 |
| 6/D/1 | final_answer | 6,155.79 | 8289 | 382 |
| 7/D/1 | final_answer | 3,698.76 | 8249 | 111 |
| 8/D/1 | final_answer | 6,102.57 | 8176 | 256 |
| 9/D/1 | final_answer | 7,072.69 | 8004 | 171 |
| 10/D/1 | final_answer | 13,699.84 | 8131 | 1448 |
| 11/D/1 | final_answer | 13,180.98 | 8219 | 535 |
| 12/D/1 | final_answer | 4,930.32 | 8292 | 224 |
| 13/D/1 | final_answer | 29,819.87 | 8308 | 556 |
| 14/D/1 | final_answer | 7,696.03 | 8296 | 368 |
| 15/D/1 | final_answer | 6,230.14 | 8316 | 428 |

### Per-method aggregates

| Method | Correct / N | Mean retrieval | Median retrieval | P95 retrieval | Mean QA | Median QA | Mean embedding | Mean model calls |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A | 10 / 15 | 1,163.75 | 1,314.78 | 2,599.83 | 42,374.86 | 33,049.25 | 1,005.07 | 4.40 |
| B | 3 / 15 | 405.08 | 385.71 | 733.53 | 11,597.38 | 6,170.77 | 333.00 | 1 |
| C | 3 / 15 | 470.88 | 328.76 | 1,963.13 | 7,210.02 | 5,988.73 | 417.86 | 1 |
| D | 4 / 15 | 2,416.64 | 2,387.26 | 3,768.27 | 11,324.82 | 8,752.10 | 712.79 | 1 |

## Excluded setup / warmup

| Q | Method | Snapshot load | Warmup | Status |
| --- | --- | --- | --- | --- |
| 1 | A | 21.93 | 571.59 | success |
| 2 | A | 128.91 | 405.61 | success |
| 3 | A | 126.54 | 458.67 | success |
| 4 | A | 108.96 | 407.94 | success |
| 5 | A | 111.14 | 385.21 | success |
| 6 | A | 108.30 | 748.86 | success |
| 7 | A | 98.76 | 684.98 | success |
| 8 | A | 56.44 | 397.51 | success |
| 9 | A | 5.56 | 327.02 | success |
| 10 | A | 24.03 | 4,123.20 | success |
| 11 | A | 62.14 | 1,329.77 | success |
| 12 | A | 99.76 | 427.59 | success |
| 13 | A | 111.90 | 402.21 | success |
| 14 | A | 101.32 | 479.87 | success |
| 15 | A | 110.75 | 4,006.51 | success |
| 1 | B | 23.22 | 644.68 | success |
| 2 | B | 138.80 | 322.12 | success |
| 3 | B | 133.12 | 1,006.78 | success |
| 4 | B | 113.33 | 354.99 | success |
| 5 | B | 101.68 | 376.30 | success |
| 6 | B | 381.45 | 395.74 | success |
| 7 | B | 116.32 | 417.50 | success |
| 8 | B | 30.44 | 267.79 | success |
| 9 | B | 12.25 | 340.92 | success |
| 10 | B | 28.67 | 274.91 | success |
| 11 | B | 54.83 | 1,181.86 | success |
| 12 | B | 131.87 | 374.50 | success |
| 13 | B | 115.36 | 375.07 | success |
| 14 | B | 108.25 | 364.25 | success |
| 15 | B | 107.32 | 396.25 | success |
| 1 | C | 17.09 | 557.73 | success |
| 2 | C | 140.45 | 378.68 | success |
| 3 | C | 85.94 | 475.13 | success |
| 4 | C | 89.02 | 442.84 | success |
| 5 | C | 77.24 | 406.56 | success |
| 6 | C | 90.75 | 336.82 | success |
| 7 | C | 72.89 | 332.71 | success |
| 8 | C | 24.75 | 288.78 | success |
| 9 | C | 4.75 | 343.36 | success |
| 10 | C | 20.94 | 344.15 | success |
| 11 | C | 40.90 | 359.52 | success |
| 12 | C | 68.43 | 402.85 | success |
| 13 | C | 399.60 | 396.85 | success |
| 14 | C | 72.66 | 1,085.75 | success |
| 15 | C | 94.55 | 1,012.80 | success |
| 1 | D | 10.55 | 7,065.52 | success |
| 2 | D | 35.88 | 2,975.68 | success |
| 3 | D | 34.52 | 2,941.90 | success |
| 4 | D | 36.60 | 2,764.76 | success |
| 5 | D | 34.99 | 2,753.62 | success |
| 6 | D | 33.04 | 2,790.27 | success |
| 7 | D | 36.24 | 3,325.62 | success |
| 8 | D | 8.62 | 2,705.19 | success |
| 9 | D | 4.77 | 2,049.31 | success |
| 10 | D | 12.96 | 2,949.24 | success |
| 11 | D | 21.72 | 2,919.44 | success |
| 12 | D | 30.82 | 2,907.34 | success |
| 13 | D | 31.81 | 2,824.67 | success |
| 14 | D | 109.54 | 3,127.00 | success |
| 15 | D | 34.52 | 3,488.20 | success |

These are excluded from timed QA calls and warm retrieval latency.

## ASR outcomes

| Provider | Successful API attempts | Failed attempts | Cache hits |
| --- | --- | --- | --- |
| deepgram-asr | 77 | 0 | 1 |
| openrouter-mai-transcribe-2 | 77 | 7 | 1 |

## Definitions and exact evidence

- [Latency measurement contract](../../scripts/MEASUREMENT.md)
- [Raw artifacts and logs](../../provenance/raw/gemini)

Warm retrieval excludes snapshot/model/index loading and the unrelated startup probe. It includes the actual question embedding, searches, fusion, lookup and reranking. Warmup is recorded separately, and never primes the benchmark question. Provider-internal model residency cannot be controlled.
