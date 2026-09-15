# Bedroom experiment: result contract

This is **M3-Bench bedroom_01**, not EgoLife. Its outputs must never be merged into the Jake DAY1 results.

## Experiment

- One fresh Gemini memory stream; 76 chronological processing segments from 73 source clips, with additional cuts at query boundaries. Offline replay runs as fast as processing permits, without real-time pacing.
- VLM sampling: 2 FPS; face preprocessing: 5 FPS. Deepgram and MAI run concurrently. HTTP connections are reused. Text embeddings are batched within each constructed clip. Two upcoming segments may prepare concurrently; graph updates remain ordered.
- All 15 user questions use the [requested query-time snapshots](QUERY_SCHEDULE.md), with Q09 approximated conservatively at 01:30 instead of 01:42. The reference answers are excluded from memory and answering prompts.
- A: uncompressed graph, normal iterative controller. B: uncompressed one-shot retrieval. C: compressed graph, one-shot retrieval. D: independently adapted Mandol hybrid retrieval and reranking, one answer call.
- A/B/C use OpenRouter `openai/text-embedding-3-large` (3072D). D independently embeds exported text with 302.ai `Qwen/Qwen3-Embedding-0.6B` (1024D), original local SPLADE, BM25, and 302.ai `Qwen/Qwen3-Reranker-0.6B`. D does not import M3 vectors.
- B/C retain the existing clip-weighted allocation of up to 20 memory text nodes. Retrieved evidence is text, grouped by clip; it is not video playback. D retains its existing top-2 results from 20 candidates.
- Answers are free text. Semantic grading runs afterward, blinded to method names, against the user-provided references. All essential multi-detail items must be present. Scores are experimental Gemini-judged scores, not official M3-Bench or human-verified accuracy; reasons and raw grading responses are preserved.
- Bounded ASR failures retain available providers; both failing allows video-only continuation. Memory API failure rolls back the segment and records a skipped segment. No alternate reasoning model is substituted.

## What to read

| Artifact | Contents |
| --- | --- |
| `results/gemini/README.md` | Observed status, committed segments, completed answers |
| `results/gemini/vlm_outputs/clip_NNNN.md` | Per-clip generated descriptions, conclusions, exact responses and attempts |
| `results/gemini/memories.md` | Human-readable integrated memory nodes |
| `results/gemini/snapshots/` | Uncompressed and compressed memory views |
| `results/gemini/retrieval.md` | Each actual question, retrieval round, query, returned text and answer |
| `results/gemini/latency.md` | Mean/median stage timings, individual measurements, setup and failures |
| `smoke_tests/preflight/` | Separate first-segment functional checks for all four methods |
| `provenance/raw/gemini/` | Exact outputs, checkpoint, logs, model/config hashes and grading evidence |
| `cache/{asr,faces,voices,media}/` | Typed reusable acquisition/features, scoped to this video |
| `scripts/` | Dedicated runners, preparation, sync, export and validation |

## Timing

Timed QA starts after loading and neutral-probe warmup. Warm retrieval includes the actual question embedding, dense/sparse search, selection/fusion, lookup and reranking. The real question is never used as its warmup probe. Offline compression, Mandol adaptation, setup, smoke tests and semantic grading are excluded. Cloud internal model residency is uncontrolled.

Record each stage's measured wall time; overlapping/nested stages must not be summed. A whole-clip embedding batch has one measured latency; no fabricated per-text latency. Preserve preprocessing service time, ready-queue time, consumer wait, ordered processing and admission-to-checkpoint time separately. Shared-GPU load is recorded because the EgoLife Qwen job may overlap this run.

Completion requires all 60 answer rows, all four warm retrieval methods, valid model/snapshot lineage, successful grading/reporting, and final validation with exit status zero. A launched tmux session is not evidence of completion.
