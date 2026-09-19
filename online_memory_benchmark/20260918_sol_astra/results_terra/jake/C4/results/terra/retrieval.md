# Jake / C4 retrieval — Terra

**Configuration:** TST speaker mapping, consolidation, and retain70. Four scheduled Jake questions completed at four graph snapshots. Accuracy is the benchmark evaluator's exact multiple-choice result.

## Retrieval performance

| Retrieval | Correct | Accuracy | Mean warm retrieval | Mean question→complete | Mean answer TTFT |
| --- | ---: | ---: | ---: | ---: | ---: |
| R1 · native StreamMeCo | 0 / 4 | 0% | 615.87 ms | 3,754.82 ms | 2,534.20 ms |
| R2 · Mandol hybrid | 2 / 4 | 50% | 2,933.62 ms | 4,313.15 ms | 719.08 ms |

R2 used the warmed Mandol worker: dense retrieval, BM25, SPLADE, RRF fusion, and 302 reranking. Its one-time adapter and index construction is excluded from the warm-retrieval figure.

## Per-question results

| Question | Reference | R1 | R1 retrieval | R2 | R2 retrieval |
| --- | --- | --- | ---: | --- | ---: |
| Who used the screwdriver first? | B | Incorrect | 439.05 ms | Incorrect | 3,135.77 ms |
| Where was the black marker in Shure's hand before? | C | Incorrect | 693.28 ms | Correct | 2,870.21 ms |
| Where was the small clapperboard on the table placed before? | D | Incorrect | 552.96 ms | Correct | 2,855.50 ms |
| Who just helped Katrina put the flowers on the table? | C | Incorrect | 778.18 ms | Incorrect | 2,873.00 ms |
