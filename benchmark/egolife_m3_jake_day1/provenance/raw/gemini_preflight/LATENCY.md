# Gemini preflight — measured latency

**All four paths passed live construction/retrieval checks.** Three clips, one question, one selected trial per method. This is a functional preflight, **not** the 10-question benchmark; no meaningful P95 or accuracy estimate can be inferred from it.

## Question → answer

| Method | Nodes | Retrieval requests | Gemini calls | Retrieval ms | Gemini ms | End-to-end ms | Answer |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A | 30 | 4 | 6 | 1,901.99 | 63,507.19 | 65,411.68 | D |
| B | 30 | 1 | 1 | 577.91 | 11,277.45 | 11,855.96 | B |
| C | 23 | 1 | 1 | 594.59 | 10,909.64 | 11,504.89 | A |
| D | 30 | 1 | 1 | 5,600.70 | 23,468.21 | 29,069.66 | B |

**A:** normal controller. **B:** uncompressed one-shot. **C:** compressed one-shot. **D:** Mandol one-shot. A used four retrievals and six Gemini calls, including its forced final answer; B/C/D each used one retrieval request and one final-answer call.

Question: “Who used the screwdriver first?” Dataset label: **B — Alice**. A/B/C/D outputs: **D/B/A/B**. Only B, D matched the label. The input covers 77.63 seconds of video, ending about 10 minutes before Q1; retrieved text does not establish who first used a screwdriver. A matching guess does not validate retrieval quality.

## Construction and offline preparation

| Clip | Clip duration s | Total construction ms | Gemini ms | Text embedding ms | Nodes after |
| --- | --- | --- | --- | --- | --- |
| 1 | 17.63 | 104,917.41 | 67,238.82 | 5,905.30 | 12 |
| 2 | 30.00 | 117,092.39 | 97,825.06 | 1,058.71 | 21 |
| 3 | 30.00 | 40,643.79 | 22,292.89 | 1,643.42 | 30 |

Three-clip construction: **262,653.59 ms** summed clip processing; Gemini: **187,356.76 ms** across **3 memory calls**. These totals exclude Python startup and artifact-export overhead.

| Offline stage | Wall ms | Details |
| --- | --- | --- |
| StreamMeCo compression | 51.51 | 30 → 23 nodes; 764,291 → 569,633 bytes; zero Gemini calls |
| M3 export | 5.53 | Text/metadata export; native vectors omitted |
| Mandol index build | 5,066.42 | Includes 2,619.94 ms across 2 embedding batches; zero reasoning calls |

## Retrieval stages

| Method / round | Embedding ms | Dense search ms | StreamMeCo scoring ms | Graph selection ms | Retrieval wall ms |
| --- | --- | --- | --- | --- | --- |
| A/1 | 569.05 | 7.11 | 0.02 | 0.16 | 576.80 |
| A/2 | 288.72 | 4.46 | 0.02 | 0.01 | 293.38 |
| A/3 | 507.27 | 4.40 | 0.02 | 0.01 | 511.93 |
| A/4 | 515.05 | 4.61 | 0.02 | 0.01 | 519.88 |
| B/1 | 570.88 | 6.47 | 0.02 | 0.15 | 577.91 |
| C/1 | 589.76 | 4.24 | 0.02 | 0.17 | 594.59 |

A/B/C use no sparse search or reranker. Query preparation and other small overheads remain in the exact per-round JSON. Controller query generation is included in the corresponding Gemini call, not counted a second time.

### Mandol internals

| Stage | Measured ms | Interpretation |
| --- | --- | --- |
| Query/MemorySpace selection | 0.13 | Candidate scope selection |
| Retriever initialization | 2,684.71 | Cold initialization inside this retrieval request |
| Dense embedding | 1,575.53 | 302.ai, 1024D |
| Dense vector search | 10.71 | Excludes remote embedding |
| BM25 backend | 14.97 | Includes lexical query processing; 0 hits is a valid no-match |
| SPLADE backend | 677.01 | Includes local query encoding and sparse search |
| RRF fusion | 0.14 | Fuses nonempty backend results |
| MemoryUnit lookup | 0.12 | Nested within backend searches |
| Candidate text/MemorySpace lookup | 0.13 | Prepares reranker inputs and provenance |
| Cloud reranker | 1,328.10 | 302.ai Qwen3 reranker |
| Total retrieval | 5,600.70 | Measured wall time; includes initialization |

**Do not add nested/parallel stages.** Dense, sparse and lookup timings overlap; total retrieval is measured independently. Offline compression/adaptation are excluded from question-to-answer latency. Non-streaming Gemini does not expose TTFT, so it is unavailable rather than zero.

## Separate embeddings and dependencies

| Methods | Embeddings | Retrieval dependencies | Reasoning |
| --- | --- | --- | --- |
| A/B/C | OpenRouter openai/text-embedding-3-large, 3072D | Native M3 graph + StreamMeCo; separate StreamMeCo Python environment | 302.ai gemini-3.8-flash |
| D | 302.ai Qwen/Qwen3-Embedding-0.6B, 1024D | Mandol environment; BM25 + original naver/splade-cocondenser-ensembledistil + Qwen/Qwen3-Reranker-0.6B | 302.ai gemini-3.8-flash |

The SPLADE checkpoint is stored under the legacy local directory `naver/splade-v3`; the downloaded source is the original cocondenser checkpoint. Mandol re-embeds text and imports **no M3 vectors**. ASR, speaker and face preprocessing retain their existing models. No Qwen/Gemma/local reasoning model ran.

## Test evidence

- Three Gemini-built clips committed, including the formerly failing third clip; 30 nodes, 7 edges.
- A/B/C/D retrieved nonempty evidence and returned a valid answer with the exact Gemini model ID.
- 26 focused tests passed; the initially skipped cross-repository test was then run explicitly and passed.
- Report/lineage validation test passed; it rejects changed snapshot hashes.
- Mandol’s initial timing wrapper failed on its lazy dense loader. That bug was fixed; the detailed-timing retest passed. Prior failures remain in provenance.

## Inspect the actual memory

- [Constructed memory and full node index](constructed_memory/README.md)
- Retrieved evidence: [A, every controller round](retrieved_memory/A.md) · [B](retrieved_memory/B.md) · [C](retrieved_memory/C.md) · [D, mapped M3 IDs](retrieved_memory/D.md)
- [Exact latency CSV](latency.csv) · [Raw test status](provenance/preflight_validation.json)
