# Jake / C1 retrieval — Terra

**Configuration:** CAM++ speaker mapping with retain50. Four scheduled Jake questions completed at four graph snapshots. Accuracy is the benchmark evaluator's exact multiple-choice result.

## Retrieval performance

| Retrieval | Correct | Accuracy | Mean warm retrieval | Mean question→complete | Mean answer TTFT |
| --- | ---: | ---: | ---: | ---: | ---: |
| R1 · native StreamMeCo | 1 / 4 | 25% | 686.72 ms | 4,390.03 ms | 2,710.69 ms |
| R2 · Mandol hybrid | 1 / 4 | 25% | 3,059.53 ms | 4,651.11 ms | 916.54 ms |

R2 used the warmed Mandol worker: dense retrieval, BM25, SPLADE, RRF fusion, and 302 reranking. Its one-time adapter and index construction is excluded from the warm-retrieval figure. Stage detail is in [latency.md](latency.md).

## Per-question results

| Question | Reference | R1 | R1 retrieval | R2 | R2 retrieval |
| --- | --- | --- | ---: | --- | ---: |
| Who used the screwdriver first? | B | Incorrect | 644.22 ms | Incorrect | 3,407.48 ms |
| Where was the black marker in Shure's hand before? | C | Incorrect | 635.23 ms | Correct | 2,929.51 ms |
| Where was the small clapperboard on the table placed before? | D | Incorrect | 688.59 ms | Incorrect | 2,767.00 ms |
| Who just helped Katrina put the flowers on the table? | C | Correct | 778.86 ms | Incorrect | 3,134.14 ms |
