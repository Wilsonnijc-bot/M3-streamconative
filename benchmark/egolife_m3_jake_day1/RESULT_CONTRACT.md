# Jake DAY1 — result contract

**Read Markdown. Keep exact evidence. Separate full benchmarks from smoke tests.**

The full 10-QA runs are [Gemini](results/gemini/README.md) and [Qwen thinking](results/qwen_thinking/README.md). Each targets **10 questions × 4 methods = 40 predictions**. A run stays in `results/` even when incomplete; its status must say what has actually finished. First-clip comparisons and other diagnostic/preflight runs belong in [smoke_tests/](smoke_tests/README.md).

## Folder structure

```text
README.md                         current progress and run links
RESULT_CONTRACT.md                this contract
results/<run>/
  README.md                       model/configuration, status, completed counts
  vlm_outputs/
    README.md                     per-clip output index
    clip_0001.md ...               generated memory, exact final text, attempts
  memories.md                     latest committed graph, rendered as text
  snapshots/q01.md ...             actual memory at each question timestamp
  snapshots/q01_compressed.md ...  compressed memory, when available
  retrieval.md                    actual questions, rounds and retrieved evidence
  latency.md                      detailed measured timing and comparisons
smoke_tests/<test>/                the same readable views for short tests
scripts/                          runners, sync/export tools and handoffs
cache/{asr,faces,voices,media,
       graphs,dependencies}/      reusable artifacts, namespaced by run
provenance/
  raw/<run>/                      original JSON/JSONL, logs and checkpoints
  vlm_outputs/<run>/              exact per-clip response/attempt extracts
  reference_data/                 small QA reference files
  relocations.json                old → new local paths
```

There is **no `inputs/` folder**. Original videos and model weights stay in their existing locations. Moving the local result presentation does not move remote checkpoints or change an experiment’s execution paths.

## Three different kinds of memory

| Artifact | Meaning |
| --- | --- |
| **Per-clip VLM output** | What the model generated for that clip: episodic descriptions, semantic conclusions, exact returned final text, and recorded attempts/errors. This is before graph integration. |
| **Committed memory** | What was actually inserted, merged, reinforced or retained in the graph after identity resolution and embedding. This can differ from the generated text. |
| **Retrieved memory** | The evidence actually returned for a particular question and retrieval round, with node IDs and Mandol → M3 mappings where applicable. |

Do not substitute one for another. An output can exist even when its segment was never committed. Overrides, failed parsing, truncation and skipped segments must remain visible. Model-generated semantic conclusions are inferences, not verified ground truth. Exact backend responses remain in provenance; readable views do not discard failed attempts or invent missing text.

Each backend builds its own memory stream once. A/B/C/D share that backend’s correctly timed snapshots; C compresses each snapshot independently and D re-embeds exported text. A later snapshot must never answer an earlier question.

## Latency rules

- Record each actual API/model call, retry, purpose, segment/question ID, token count and elapsed time. Use unavailable values for measurements that were not exposed.
- Measure **warm retrieval with an uncached actual question**. Snapshot/model/index loading and an unrelated warmup probe are recorded separately, outside timed QA. The actual question’s embedding, searches, scoring, graph lookup, fusion and reranking remain included.
- Keep controller/final-answer time separate from retrieval time. A reports every controller round; B/C/D each retain one actual question retrieval request and one answer call.
- Measure concurrent Deepgram/MAI calls individually and their combined wall time independently. Do not add their overlapping durations as ASR-stage latency.
- Measure the whole per-clip text-embedding batch, its input count and attempts. **Batch latency divided by text count is not individual-text latency.**
- Distinguish preparation work, waiting for preparation, waiting for chronological processing, ordered processing, and admission-to-checkpoint latency. **Throughput is a separate metric.**
- Label cache hits, cold versus warm runs, execution-policy changes and GPU contention. Never pool those conditions into an unlabeled comparison or treat cached acquisition as fresh provider latency.
- Keep FPS/model settings explicit. A backend change plus a sampling change is not a model-only comparison.

See [the timing definitions](scripts/gemini/MEASUREMENT.md) for exact event fields.

## Status and failures

A successful startup, preflight or shell exit is not a finished benchmark. Completion requires the ten snapshots, all four methods, 40 verified predictions, required artifacts and validation. During execution, show actual committed segments, saved snapshots and QA rows.

Failures are recorded before continuing according to the run’s policy. A rolled-back segment must not leave partial graph changes. Missing/degraded coverage must appear in the snapshots and comparisons, shared consistently by all methods. Unknown values stay unknown; missing answers are not counted as completed predictions.

## Refresh and preservation

`python3 scripts/sync_run.py gemini` refreshes remote artifacts into this layout; `python3 scripts/render_results.py` rebuilds the readable views from local evidence. The sync watcher maintains the same contract. Scripts and caches must not reappear as loose files inside result folders.

Markdown is the inspection layer. Raw JSON, exact checkpoints, original responses, hashes and logs remain the reproducibility layer. Regeneration must preserve their content and keep all published links valid.
