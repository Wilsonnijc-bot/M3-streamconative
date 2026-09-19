# Jake / C2 retrieval — Terra

**Configuration:** TST speaker mapping with retain50. Four scheduled Jake questions completed at four graph snapshots. Accuracy is the benchmark evaluator's exact multiple-choice result.

## Retrieval performance

| Retrieval | Correct | Accuracy | Mean warm retrieval | Mean question→complete | Mean answer TTFT |
| --- | ---: | ---: | ---: | ---: | ---: |
| R1 · native StreamMeCo | 1 / 4 | 25% | 572.70 ms | 4,834.65 ms | 3,574.05 ms |
| R2 · Mandol hybrid | 1 / 4 | 25% | 2,889.62 ms | 4,677.10 ms | 1,194.57 ms |

R2 used the warmed Mandol worker: dense retrieval, BM25, SPLADE, RRF fusion, and 302 reranking. Its one-time adapter and index construction is excluded from the warm-retrieval figure. Stage detail is in [latency.md](latency.md).

## Per-question results

| Question | Reference | R1 | R1 retrieval | R2 | R2 retrieval |
| --- | --- | --- | ---: | --- | ---: |
| Who used the screwdriver first? | B | Incorrect | 395.60 ms | Incorrect | 3,043.33 ms |
| Where was the black marker in Shure's hand before? | C | Incorrect | 552.54 ms | Incorrect | 2,894.22 ms |
| Where was the small clapperboard on the table placed before? | D | Correct | 598.58 ms | Correct | 2,778.95 ms |
| Who just helped Katrina put the flowers on the table? | C | Incorrect | 744.09 ms | Incorrect | 2,841.98 ms |
