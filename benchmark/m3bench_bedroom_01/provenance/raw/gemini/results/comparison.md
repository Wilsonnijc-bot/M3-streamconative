# M3-Bench bedroom_01 — Gemini fifteen open-ended questions

Reasoning: `gemini-3.8-flash` via 302.ai. A/B/C use M3 native OpenRouter text-embedding-3-large; D independently embeds exported text with 302.ai Qwen3-Embedding-0.6B (1024D), local original SPLADE and BM25, then Qwen3-Reranker-0.6B.

All QA rows measure warm local retrieval with an uncached question. Snapshot loading, offline adaptation/compression, and fixed neutral-probe warmup are excluded and recorded in retrieval_warmup.jsonl. Actual query embeddings, searches and reranking remain timed; cloud-provider internal model state is not controlled. Mandol backend times include nested embeddings and unit lookup; parallel/nested timings are not additive. Retrieval total is measured wall time. TTFT is unavailable for the non-streaming API. Compression and adaptor use zero reasoning calls.

| Latency mode | Skipped segments | ASR degraded segments | Q | Method | Memory nodes | Retrieval queries | Gemini calls | Embed ms | Dense ms | Sparse ms | StreamMeCo/Mandol ms | Graph lookup ms | Rerank ms | Retrieval total ms | Gemini answer/controller ms | End-to-end ms | Answer | Correct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| warm_retrieval_uncached_question | 0 | 0 | 1 | A | 147 | 4 | 6 | 1157.83 | 66.44 | 0.00 | 0.42 | 0.46 | 0.00 | 1226.49 | 37656.28 | 38885.27 | Taller one | True |
| warm_retrieval_uncached_question | 0 | 0 | 1 | B | 147 | 1 | 1 | 295.60 | 40.15 | 0.00 | 0.24 | 0.42 | 0.00 | 336.90 | 5896.27 | 6234.06 | The retrieved memories are insufficient to answer this question. | False |
| warm_retrieval_uncached_question | 0 | 0 | 1 | C | 115 | 1 | 1 | 265.82 | 13.23 | 0.00 | 0.10 | 0.34 | 0.00 | 279.83 | 5060.87 | 5341.33 | The retrieved memories are insufficient to determine whether Emma's coat should be placed on the taller or shorter coat rack. | False |
| warm_retrieval_uncached_question | 0 | 0 | 1 | D | 143 | 1 | 1 | 751.17 | 8.09 | 28.72 | 0.31 | 0.44 | 1646.90 | 2413.63 | 9166.50 | 11581.03 | Based on the retrieved memories, there is insufficient information to determine whether Emma's coat should be placed on the taller or shorter coat rack. | False |
| warm_retrieval_uncached_question | 0 | 0 | 2 | A | 725 | 1 | 2 | 305.15 | 78.86 | 0.00 | 0.65 | 0.92 | 0.00 | 386.16 | 10126.09 | 10513.20 | No, Emma's tidying up habit is not good. | True |
| warm_retrieval_uncached_question | 0 | 0 | 2 | B | 725 | 1 | 1 | 278.03 | 82.36 | 0.00 | 0.63 | 3.53 | 0.00 | 365.13 | 5805.13 | 6170.77 | No. The memories indicate her tidying habit is not good, as someone is frustrated by a cluttered desk and suspects Emma caused it. | True |
| warm_retrieval_uncached_question | 0 | 0 | 2 | C | 563 | 1 | 1 | 329.50 | 60.28 | 0.00 | 0.64 | 0.87 | 0.00 | 391.84 | 5602.37 | 5994.74 | No, Emma's tidying up habit does not appear to be good; another woman is frustrated by the cluttered condition of a desk and suspects Emma caused it. | True |
| warm_retrieval_uncached_question | 0 | 0 | 2 | D | 715 | 1 | 1 | 640.62 | 5.92 | 17.64 | 0.53 | 1.01 | 1731.34 | 2387.26 | 3511.50 | 5899.72 | Based on the retrieved memories, no, Emma’s tidying up habit does not seem good; another woman was frustrated by a cluttered desk suspected to have been caused by Emma and had to remind her to throw something into the bin. | True |
| warm_retrieval_uncached_question | 0 | 0 | 3 | A | 725 | 2 | 3 | 821.77 | 172.08 | 0.00 | 1.36 | 1.79 | 0.00 | 998.18 | 17862.88 | 18862.45 | Emma’s mother places heavy stress and high expectations on Emma’s academic performance and grades. | True |
| warm_retrieval_uncached_question | 0 | 0 | 3 | B | 725 | 1 | 1 | 325.60 | 78.67 | 0.00 | 0.72 | 0.96 | 0.00 | 406.58 | 88761.82 | 89168.91 | Emma’s mother stresses heavily over her academic performance. | False |
| warm_retrieval_uncached_question | 0 | 0 | 3 | C | 563 | 1 | 1 | 256.89 | 69.67 | 0.00 | 0.77 | 0.85 | 0.00 | 328.76 | 16441.76 | 16771.18 | Emma’s mother stresses heavily over her academic performance. | False |
| warm_retrieval_uncached_question | 0 | 0 | 3 | D | 715 | 1 | 1 | 740.65 | 7.94 | 19.23 | 0.70 | 1.00 | 1624.47 | 2381.73 | 5372.50 | 7755.85 | Emma’s mother places high pressure and expectations on her academic studies, stressing heavily over her academic performance. | True |
| warm_retrieval_uncached_question | 0 | 0 | 4 | A | 725 | 4 | 6 | 2342.39 | 250.19 | 0.00 | 2.42 | 2.57 | 0.00 | 2599.83 | 98886.45 | 101489.33 | Creativity (creative ability) | False |
| warm_retrieval_uncached_question | 0 | 0 | 4 | B | 725 | 1 | 1 | 308.94 | 83.16 | 0.00 | 0.70 | 0.95 | 0.00 | 394.37 | 5133.45 | 5528.39 | The retrieved memories are insufficient to answer this question. | False |
| warm_retrieval_uncached_question | 0 | 0 | 4 | C | 563 | 1 | 1 | 246.55 | 70.60 | 0.00 | 0.77 | 0.92 | 0.00 | 320.49 | 15350.00 | 15671.84 | Based on the retrieved memories, the information is insufficient to answer what Lily thinks is the most important ability of a designer. | False |
| warm_retrieval_uncached_question | 0 | 0 | 4 | D | 715 | 1 | 1 | 744.11 | 6.06 | 20.28 | 0.45 | 1.10 | 1615.80 | 2372.81 | 9658.28 | 12033.16 | Based on the retrieved memories, the information is insufficient to answer what Lily thinks is the most important ability of a designer. | False |
| warm_retrieval_uncached_question | 0 | 0 | 5 | A | 725 | 1 | 2 | 245.53 | 79.38 | 0.00 | 0.91 | 0.99 | 0.00 | 327.42 | 14302.04 | 14630.35 | ** Emma plans to improve her programming skills by working on hands-on programming projects and participating in programming competitions. | False |
| warm_retrieval_uncached_question | 0 | 0 | 5 | B | 725 | 1 | 1 | 354.02 | 100.39 | 0.00 | 0.91 | 1.04 | 0.00 | 457.04 | 8573.05 | 9030.76 | Emma plans to work on programming projects, share her first successful project, and participate in programming competitions. | False |
| warm_retrieval_uncached_question | 0 | 0 | 5 | C | 563 | 1 | 1 | 305.78 | 63.97 | 0.00 | 0.63 | 0.88 | 0.00 | 371.79 | 6575.33 | 6947.68 | Based on the retrieved memories, Emma plans to work on programming projects, share her first successful project, and participate in programming competitions. | False |
| warm_retrieval_uncached_question | 0 | 0 | 5 | D | 715 | 1 | 1 | 636.60 | 3.69 | 24.39 | 0.52 | 1.30 | 1607.89 | 2255.99 | 7304.80 | 9562.34 | Emma plans to improve her programming skills by sharing her first successful project and participating in programming/technical competitions. | False |
| warm_retrieval_uncached_question | 0 | 0 | 6 | A | 725 | 1 | 2 | 278.20 | 79.22 | 0.00 | 0.69 | 0.94 | 0.00 | 359.63 | 9022.44 | 9382.94 | Lily likes mocha. | True |
| warm_retrieval_uncached_question | 0 | 0 | 6 | B | 725 | 1 | 1 | 289.55 | 95.14 | 0.00 | 0.80 | 0.98 | 0.00 | 387.23 | 9378.20 | 9766.11 | Based on the retrieved memories, the information is insufficient to determine what kind of coffee Lily likes. | False |
| warm_retrieval_uncached_question | 0 | 0 | 6 | C | 563 | 1 | 1 | 219.26 | 74.15 | 0.00 | 0.68 | 0.87 | 0.00 | 295.55 | 10552.04 | 10848.07 | Based on the retrieved memories, Lily likes mocha (she orders a mocha). | True |
| warm_retrieval_uncached_question | 0 | 0 | 6 | D | 715 | 1 | 1 | 617.56 | 6.03 | 17.93 | 0.44 | 1.04 | 1647.92 | 2278.12 | 6155.79 | 8435.46 | Based on the retrieved memories, Lily likes mocha (she orders a mocha). | True |
| warm_retrieval_uncached_question | 0 | 0 | 7 | A | 725 | 4 | 6 | 1159.97 | 326.87 | 0.00 | 3.00 | 3.04 | 0.00 | 1495.42 | 28181.83 | 29680.47 | Computer Science | True |
| warm_retrieval_uncached_question | 0 | 0 | 7 | B | 725 | 1 | 1 | 280.03 | 83.90 | 0.00 | 0.97 | 0.94 | 0.00 | 366.44 | 8663.78 | 9030.83 | The retrieved memories do not specify Emma's major, though they mention her interest and background in coding and computer science. Therefore, the memories are insufficient to give a definitive answer. | False |
| warm_retrieval_uncached_question | 0 | 0 | 7 | C | 563 | 1 | 1 | 659.15 | 72.64 | 0.00 | 0.68 | 0.84 | 0.00 | 733.90 | 5254.33 | 5988.73 | The retrieved memories are insufficient to determine Emma's major. | False |
| warm_retrieval_uncached_question | 0 | 0 | 7 | D | 715 | 1 | 1 | 661.43 | 5.84 | 19.74 | 0.47 | 1.31 | 1635.86 | 2310.28 | 3698.76 | 6010.06 | The retrieved memories are insufficient to determine Emma's major. | False |
| warm_retrieval_uncached_question | 0 | 0 | 8 | A | 147 | 4 | 6 | 1240.88 | 71.57 | 0.00 | 0.49 | 0.44 | 0.00 | 1314.78 | 85319.93 | 86637.40 | shorter one | True |
| warm_retrieval_uncached_question | 0 | 0 | 8 | B | 147 | 1 | 1 | 353.34 | 18.54 | 0.00 | 0.19 | 0.35 | 0.00 | 372.83 | 5144.88 | 5518.37 | The retrieved memories are insufficient to answer this question, as they do not mention whether the coat rack is the taller or shorter one. | False |
| warm_retrieval_uncached_question | 0 | 0 | 8 | C | 115 | 1 | 1 | 221.69 | 16.15 | 0.00 | 0.10 | 0.47 | 0.00 | 238.74 | 3949.87 | 4189.09 | Based on the retrieved memories, the information is insufficient to determine whether Emma's hat should be placed on the taller or shorter coat rack. | False |
| warm_retrieval_uncached_question | 0 | 0 | 8 | D | 143 | 1 | 1 | 783.85 | 4.87 | 20.28 | 0.32 | 0.42 | 1642.86 | 2439.31 | 6102.57 | 8542.89 | Based on the retrieved memories, there is insufficient information to determine whether Emma's hat should be placed on the taller or shorter coat rack. | False |
| warm_retrieval_uncached_question | 0 | 0 | 9 | A | 31 | 4 | 6 | 1445.51 | 18.40 | 0.00 | 0.10 | 0.20 | 0.00 | 1465.06 | 91401.48 | 92868.95 | 4:00 PM | True |
| warm_retrieval_uncached_question | 0 | 0 | 9 | B | 31 | 1 | 1 | 258.78 | 4.19 | 0.00 | 0.02 | 0.12 | 0.00 | 263.23 | 2576.10 | 2839.77 | The retrieved memories are insufficient to answer when Lily originally needs afternoon tea. | False |
| warm_retrieval_uncached_question | 0 | 0 | 9 | C | 25 | 1 | 1 | 346.10 | 3.97 | 0.00 | 0.02 | 0.18 | 0.00 | 350.49 | 3097.17 | 3448.16 | Based on the retrieved memories, the information is insufficient to answer when Lily originally needs afternoon tea. | False |
| warm_retrieval_uncached_question | 0 | 0 | 9 | D | 31 | 1 | 1 | 631.89 | 4.01 | 18.75 | 0.15 | 0.09 | 860.24 | 1498.71 | 7072.69 | 8572.18 | The retrieved memories are insufficient to answer this question. | False |
| warm_retrieval_uncached_question | 0 | 0 | 10 | A | 248 | 4 | 6 | 1217.50 | 114.99 | 0.00 | 0.96 | 0.95 | 0.00 | 1335.97 | 40338.82 | 41677.45 | McDonald's fries, a slice of cake, bread slices, and coffee. | False |
| warm_retrieval_uncached_question | 0 | 0 | 10 | B | 248 | 1 | 1 | 401.55 | 29.07 | 0.00 | 0.33 | 0.51 | 0.00 | 431.95 | 6094.67 | 6527.18 | Based on the retrieved memories, "Lily" is not mentioned, so the memories are insufficient to answer what is included in her afternoon tea. | False |
| warm_retrieval_uncached_question | 0 | 0 | 10 | C | 193 | 1 | 1 | 212.16 | 22.11 | 0.00 | 0.20 | 0.41 | 0.00 | 235.27 | 3761.68 | 3997.45 | The retrieved memories are insufficient to answer the question, as Lily is not mentioned. | False |
| warm_retrieval_uncached_question | 0 | 0 | 10 | D | 242 | 1 | 1 | 746.65 | 2.63 | 19.73 | 0.37 | 1.23 | 3010.97 | 3768.27 | 13699.84 | 17470.27 | While Lily is not mentioned by name, the afternoon tea ordered and prepared in the memories includes:

* **Coffee** (specifically a mocha)
* **Fries** (with ketchup)
* **Strawberry cake**
* **Bread slices** 

*(Note: If "Lily" refers to someone else, the memories are insufficient to identify her.)* | False |
| warm_retrieval_uncached_question | 0 | 0 | 11 | A | 442 | 4 | 5 | 1275.65 | 206.87 | 0.00 | 1.75 | 1.62 | 0.00 | 1487.90 | 31558.95 | 33049.25 | Emma's afternoon tea consists of french fries, cake, and coffee. | False |
| warm_retrieval_uncached_question | 0 | 0 | 11 | B | 442 | 1 | 1 | 638.91 | 92.80 | 0.00 | 0.49 | 0.77 | 0.00 | 733.53 | 5820.45 | 6554.55 | Based on the retrieved memories, the afternoon tea served at the table consists of a slice of cake, snacks, and a drink in a mug (with available afternoon tea items noted as coffee, fries, and cakes). | False |
| warm_retrieval_uncached_question | 0 | 0 | 11 | C | 345 | 1 | 1 | 243.26 | 43.69 | 0.00 | 0.44 | 0.61 | 0.00 | 288.56 | 6566.88 | 6855.92 | The retrieved memories are insufficient to determine specifically what Emma's afternoon tea is. (The memories only note that available afternoon tea items include coffee, fries, and cakes, and that snacks, a cake slice, a mug, and bottles were on the table). | False |
| warm_retrieval_uncached_question | 0 | 0 | 11 | D | 432 | 1 | 1 | 684.46 | 3.26 | 23.69 | 0.55 | 0.98 | 1591.74 | 2285.31 | 13180.98 | 15467.48 | The retrieved memories are insufficient to specify what Emma's afternoon tea is (though available afternoon tea items listed include coffee, fries, and cakes). | False |
| warm_retrieval_uncached_question | 0 | 0 | 12 | A | 725 | 1 | 2 | 291.13 | 81.47 | 0.00 | 0.67 | 1.02 | 0.00 | 374.90 | 11334.60 | 11710.39 | Lily was supportive, understanding, and reassuring toward Emma, offering comfort and encouragement rather than being critical. | False |
| warm_retrieval_uncached_question | 0 | 0 | 12 | B | 725 | 1 | 1 | 227.77 | 83.91 | 0.00 | 0.77 | 0.92 | 0.00 | 313.99 | 4058.45 | 4372.94 | Lily had a supportive and reassuring attitude; she offered Emma comfort and encouragement, reassuring her that failing an exam is not the end of the world. | False |
| warm_retrieval_uncached_question | 0 | 0 | 12 | C | 563 | 1 | 1 | 1897.64 | 63.23 | 0.00 | 0.71 | 0.96 | 0.00 | 1963.13 | 4410.44 | 6374.12 | Lily had a reassuring and supportive attitude, comforting Emma and reassuring her that failing an exam is not the end of the world. | False |
| warm_retrieval_uncached_question | 0 | 0 | 12 | D | 715 | 1 | 1 | 720.70 | 7.52 | 20.17 | 0.96 | 1.14 | 1694.71 | 2436.74 | 4930.32 | 7369.23 | Lily was supportive, empathetic, and reassuring, offering comfort, patience, and emotional support to help soothe Emma. | False |
| warm_retrieval_uncached_question | 0 | 0 | 13 | A | 725 | 4 | 6 | 1564.57 | 368.27 | 0.00 | 2.98 | 3.03 | 0.00 | 1941.30 | 42797.40 | 44741.69 | No, Emma's allergy is not serious. | True |
| warm_retrieval_uncached_question | 0 | 0 | 13 | B | 725 | 1 | 1 | 295.24 | 84.89 | 0.00 | 0.82 | 0.93 | 0.00 | 382.52 | 3637.11 | 4020.20 | Based on the retrieved memories, the information is insufficient to determine if Emma's allergy is serious. (The memories only mention an inquiry about the severity of her allergic reaction during an exam, but do not state the answer.) | False |
| warm_retrieval_uncached_question | 0 | 0 | 13 | C | 563 | 1 | 1 | 245.09 | 65.28 | 0.00 | 0.68 | 0.87 | 0.00 | 312.52 | 4070.54 | 4383.61 | Based on the retrieved memories, the information is insufficient to determine whether Emma's allergy is serious. (The memories only mention that she ate an allergen and that someone inquired about the severity of her allergic reaction, but they do not state the severity.) | False |
| warm_retrieval_uncached_question | 0 | 0 | 13 | D | 715 | 1 | 1 | 721.09 | 5.34 | 19.48 | 0.42 | 1.03 | 1709.76 | 2442.83 | 29819.87 | 32263.81 | The provided memories are insufficient to determine whether Emma's allergy is serious; they only note that she had an allergic reaction to strawberries during an exam and did not anticipate the severity of the reaction. | False |
| warm_retrieval_uncached_question | 0 | 0 | 14 | A | 725 | 1 | 2 | 444.81 | 80.47 | 0.00 | 0.86 | 0.94 | 0.00 | 527.71 | 12564.23 | 13092.81 | Designer | True |
| warm_retrieval_uncached_question | 0 | 0 | 14 | B | 725 | 1 | 1 | 387.77 | 88.43 | 0.00 | 0.85 | 0.94 | 0.00 | 478.70 | 2785.20 | 3264.42 | Lily is a designer. | True |
| warm_retrieval_uncached_question | 0 | 0 | 14 | C | 563 | 1 | 1 | 459.92 | 62.78 | 0.00 | 0.62 | 0.88 | 0.00 | 524.77 | 5051.95 | 5577.24 | The retrieved memories are insufficient to determine Lily's occupation. | False |
| warm_retrieval_uncached_question | 0 | 0 | 14 | D | 715 | 1 | 1 | 811.42 | 5.60 | 18.70 | 0.60 | 1.07 | 1631.18 | 2458.64 | 7696.03 | 10156.65 | The retrieved memories are insufficient to determine Lily's occupation. | False |
| warm_retrieval_uncached_question | 0 | 0 | 15 | A | 725 | 4 | 6 | 1285.14 | 321.70 | 0.00 | 3.13 | 3.00 | 0.00 | 1615.57 | 86782.50 | 88401.02 | Yes, Lily likes her job. | True |
| warm_retrieval_uncached_question | 0 | 0 | 15 | B | 725 | 1 | 1 | 299.89 | 83.53 | 0.00 | 0.70 | 1.00 | 0.00 | 385.71 | 5547.06 | 5933.39 | Yes. Although she finds it exhausting and stressful due to deadlines, Lily remains passionate about her work, deeply appreciates the creative process, and takes pride in completing her design work. | True |
| warm_retrieval_uncached_question | 0 | 0 | 15 | C | 563 | 1 | 1 | 359.07 | 66.32 | 0.00 | 0.67 | 0.87 | 0.00 | 427.54 | 5333.12 | 5761.15 | Yes, Lily remains passionate and energetic about her work despite it being exhausting. | True |
| warm_retrieval_uncached_question | 0 | 0 | 15 | D | 715 | 1 | 1 | 799.67 | 8.18 | 18.69 | 0.97 | 1.16 | 1699.04 | 2519.95 | 6230.14 | 8752.10 | Yes, she remains passionate and energetic about her work, though she acknowledges it can be exhausting, stressful, and difficult. | True |

## Per-method aggregates

```json
{
  "A": {
    "correct": 10,
    "questions": 15,
    "mean_retrieval_ms": 1163.7538810008361,
    "median_retrieval_ms": 1314.7792529925937,
    "p95_retrieval_ms": 2599.829470011173,
    "mean_end_to_end_ms": 42374.863471867866,
    "median_end_to_end_ms": 33049.245675007114,
    "mean_embedding_ms": 1005.067885730144,
    "mean_gemini_ms_per_question": 41209.060422400944,
    "mean_gemini_ms_per_call": 9365.69555054567,
    "mean_gemini_calls": 4.4,
    "mean_retrieval_queries": 2.8666666666666667
  },
  "B": {
    "correct": 3,
    "questions": 15,
    "mean_retrieval_ms": 405.077490467617,
    "median_retrieval_ms": 385.7116400031373,
    "p95_retrieval_ms": 733.5341839934699,
    "mean_end_to_end_ms": 11597.37607333227,
    "median_end_to_end_ms": 6170.772812998621,
    "mean_embedding_ms": 333.00151699998725,
    "mean_gemini_ms_per_question": 11191.707784332297,
    "mean_gemini_ms_per_call": 11191.707784332297,
    "mean_gemini_calls": 1,
    "mean_retrieval_queries": 1
  },
  "C": {
    "correct": 3,
    "questions": 15,
    "mean_retrieval_ms": 470.87905319834437,
    "median_retrieval_ms": 328.76439500250854,
    "p95_retrieval_ms": 1963.1320320040686,
    "mean_end_to_end_ms": 7210.020325464818,
    "median_end_to_end_ms": 5988.731335004559,
    "mean_embedding_ms": 417.85723926732317,
    "mean_gemini_ms_per_question": 6738.557443468017,
    "mean_gemini_ms_per_call": 6738.557443468017,
    "mean_gemini_calls": 1,
    "mean_retrieval_queries": 1
  },
  "D": {
    "correct": 4,
    "questions": 15,
    "mean_retrieval_ms": 2416.6387255322966,
    "median_retrieval_ms": 2387.2626129887067,
    "p95_retrieval_ms": 3768.2688609929755,
    "mean_end_to_end_ms": 11324.815623598988,
    "median_end_to_end_ms": 8752.101724996464,
    "mean_embedding_ms": 712.7919656680509,
    "mean_gemini_ms_per_question": 8906.70481173341,
    "mean_gemini_ms_per_call": 8906.70481173341,
    "mean_gemini_calls": 1,
    "mean_retrieval_queries": 1
  }
}
```
