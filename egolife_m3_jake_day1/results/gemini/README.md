# Gemini — first ten questions

**Complete: 40 verified QA predictions** · updated 2026-09-15T03:12:56+00:00

Model: `gemini-3.8-flash`. Saved committed segment audits: **144**; latest segment: **144**; query snapshots: **10/10**; actual QA rows: **40/40**.

- [Per-clip VLM outputs](vlm_outputs/README.md) — generated descriptions, exact final text and all recorded attempts.
- [Memories](memories.md) — compact nodes, connections, and character mappings.
- [Reusable graph-to-Markdown exporter](../../../StreamMeCo/mmagent/videograph_markdown.md).
- [Latency](latency.md) — construction, preprocessing, batch, queue and retrieval stages.
- [Retrieved memories](retrieval.md) — actual questions, rounds and evidence.
- [Raw provenance](../../provenance/raw/gemini) · [Run scripts](../../scripts/runs/gemini)

- [Memory replays at 20, 40 and 60 minutes](replays/README.md).

**Method D:** up to **100 candidates → 20 final evidence nodes**, Qwen embedding and reranking via **302.ai**. These are the later rerun measurements; A/B/C retain their original measurements. The earlier two-node D result is retained only in provenance.
