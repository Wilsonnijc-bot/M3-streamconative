# M3-Bench bedroom_01 — Gemini, 15 open-ended questions

**Complete: 60 verified QA predictions** · updated 2026-09-15T02:57:26+00:00

Model: `gemini-3.8-flash`. Saved committed segment audits: **76**; latest segment: **76**; query snapshots: **15/15**; actual QA rows: **60/60**.

- [Per-clip VLM outputs](vlm_outputs/README.md) — generated descriptions, exact final text and all recorded attempts.
- [Memories](memories.md) — readable graph contents and query-time snapshots.
- [Latency](latency.md) — construction, preprocessing, batch, queue and retrieval stages.
- [Retrieved memories](retrieval.md) — actual questions, rounds and evidence.
- [Raw provenance](../../provenance/raw/gemini)

Prepared source clips: **73/73**. These are media preparation counts, separate from committed memory segments.

[Query timestamps and approximation](../../QUERY_SCHEDULE.md).
Answers are open-ended; correctness is scored separately by Gemini against the reference, with grading excluded from QA latency. [Experiment contract](../../RESULT_CONTRACT.md).

**Method D:** up to **100 candidates → 20 final evidence nodes**, Qwen embedding and reranking via **302.ai**. These are the later rerun measurements; A/B/C retain their original measurements. The earlier two-node D result is retained only in provenance.
