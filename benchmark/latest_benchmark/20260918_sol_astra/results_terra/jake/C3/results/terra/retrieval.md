# Jake / C3 retrieval — Terra

**Configuration:** TST speaker mapping, consolidation, and retain50. Four scheduled Jake questions completed at four graph snapshots; the first two scheduled consolidations completed before the worker paused. Accuracy is the benchmark evaluator's exact multiple-choice result.

## Retrieval performance

| Retrieval | Correct | Accuracy | Mean warm retrieval | Mean question→complete | Mean answer TTFT |
| --- | ---: | ---: | ---: | ---: | ---: |
| R1 · native StreamMeCo | 2 / 4 | 50% | 743.68 ms | 4,394.76 ms | 3,001.19 ms |
| R2 · Mandol hybrid | 0 / 4 | 0% | 2,912.38 ms | 4,413.61 ms | 998.56 ms |

R2 used the warmed Mandol worker: dense retrieval, BM25, SPLADE, RRF fusion, and 302 reranking. Its one-time adapter and index construction is excluded from the warm-retrieval figure. Stage detail, including both consolidations, is in [latency.md](latency.md).

## Per-question results

| Question | Reference | R1 | R1 retrieval | R2 | R2 retrieval |
| --- | --- | --- | ---: | --- | ---: |
| Who used the screwdriver first? | B | Incorrect | 682.93 ms | Incorrect | 2,996.11 ms |
| Where was the black marker in Shure's hand before? | C | Incorrect | 713.29 ms | Incorrect | 3,047.45 ms |
| Where was the small clapperboard on the table placed before? | D | Correct | 843.00 ms | Incorrect | 2,784.68 ms |
| Who just helped Katrina put the flowers on the table? | C | Correct | 735.51 ms | Incorrect | 2,821.26 ms |
