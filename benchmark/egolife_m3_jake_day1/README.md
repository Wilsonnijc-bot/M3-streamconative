# Jake DAY1 experiments

Updated: 2026-09-15T16:00:47+00:00. Start with a run below; memories and detailed latency are Markdown.

| Full benchmark | State | Latest segment | Snapshots | QA rows |
| --- | --- | --- | --- | --- |
| [Gemini — first ten questions](results/gemini/README.md) | Complete: 40 verified QA predictions | 144 | 10 | 40 |
| [Qwen3.5 4B thinking + identity prompt — first ten questions](results/qwen_thinking/README.md) | Stopped after failure; incomplete benchmark | 144 | 10 | 40 |

[Smoke tests: first-clip comparisons, preflights and short Qwen checks](smoke_tests/README.md). These are separate from the full 10-question runs.

## Result contract

[Read the result contract](RESULT_CONTRACT.md).

```text
scripts/                    runners, sync/export tools, handoffs
cache/
  asr/                      provider transcripts, namespaced by run
  faces/                    face detections/features
  voices/                   speaker features and segmented audio
  media/                    prepared/cropped media
  graphs/                   intermediate binary graph caches
  dependencies/             downloaded test/runtime dependencies
results/<run>/
  README.md                 status and entry point
  vlm_outputs/clip_NNNN.md   per-clip model output and attempt history
  memories.md               latest graph as readable text
  snapshots/q01.md ...      exact query-time memory views
  latency.md                detailed timing with scope definitions
  retrieval.md              actual retrieved memories per question/round
smoke_tests/<test>/         first-clip comparisons, preflights and short checks
provenance/                 exact JSON, checkpoints, manifests and logs
```

Original videos remain outside this result folder; small QA reference files are under provenance/reference_data. No model weights or remote experiment paths were moved. The remote process continues using its existing checkpoint locations. Different Qwen configurations stay separate; they are not merged into one result. Existing cold-start preflight measurements stay labeled separately from warm-query evaluations.

## Refresh

```bash
python3 scripts/sync_run.py gemini
```

Run that command from this folder, or use its absolute path. The Gemini transfer watcher also updates this layout. Caches are reusable only when provider/model, audio, sampling and schema match; never reuse graph-assigned IDs across different memory constructions.

- [Old → new path mapping](provenance/relocations.json)
- [Latency measurement definitions](scripts/gemini/MEASUREMENT.md)
