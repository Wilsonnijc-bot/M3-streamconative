# Qwen3.5 4B thinking + identity prompt — first ten questions

**Stopped after failure; incomplete benchmark** · updated 2026-09-15T16:00:47+00:00

Model: `Qwen/Qwen3.5-4B`. Saved committed segment audits: **141**; latest segment: **144**; query snapshots: **10/10**; actual QA rows: **40/40**.

- [Per-clip VLM outputs](vlm_outputs/README.md) — generated descriptions, exact final text and all recorded attempts.
- [Memories](memories.md) — compact nodes, connections, and character mappings.
- [Reusable graph-to-Markdown exporter](../../../StreamMeCo/mmagent/videograph_markdown.md).
- [Latency](latency.md) — construction, preprocessing, batch, queue and retrieval stages.
- [Retrieved memories](retrieval.md) — actual questions, rounds and evidence.
- [Raw provenance](../../provenance/raw/qwen_thinking) · [Run scripts](../../scripts/runs/qwen_thinking)

**Configuration:** memory construction thinking enabled; QA thinking **disabled (user-requested QA restart)**; 2 FPS VLM sampling; Qwen-only identity prompt v2; 16,384-token output budget. Gemini may share the GPU, so latency can include contention.

[Exact Qwen-specific prompt](../../provenance/raw/qwen_thinking/qwen_identity_system_prompt.md) · [Memory lineage and known attribution limitations](../../provenance/raw/qwen_thinking/memory_resume_manifest.json) · [Gemini prompt hash verification](../../provenance/raw/qwen_thinking/gemini_prompt_unchanged.txt)

**Mandol Method D:** candidate pool **100**, final results **20**. [Effective retrieval configuration](../../provenance/raw/qwen_thinking/results/mandol_retrieval_config.json)
