# Online long-horizon memory benchmark — Terra / Sol

Local root: `online_memory_benchmark/20260918_sol_astra`.
Remote root: `/opt/streammeco/run/online_memory_benchmark/20260918_sol_astra`.
Hyperstack: `1042997`, NVIDIA RTX A6000 48 GB.

Execution status is recorded in `metadata/current_session.txt`,
`metadata/current_log.txt`, and the session-specific `.status` / `.exit_status`
files. `metadata/launch_observation.json` records the last verified process state.
Full results belong under `results/`; diagnostic validation belongs under `smoke/`.
A running tmux session is not evidence of benchmark completion.

The normalized manifests contain all 102 Jake Day 1 questions from the user-linked Hugging Face dataset and 1,000 AEA questions selected by evenly spaced ranks across the existing timeline.
AEA uses the existing derived causal QA schedule, not invented annotation times.
Jake uses seconds from the first recording's wall-clock start and preserves
recording gaps; AEA uses its manifest's assembled stream offsets. A tiny MP4
container tail with no video frame is an explicit gap, so same-time queries use
the last valid committed observations. TST uses no pre-enrollment and excludes no enrollment/calibration intervals. Inspect `configs/media/`, the saved event plans, and
`metadata/*_video_availability.json` for exact bounds.

## Implementation

`Benchmarksep18.md` and the attached continuation request define the run. The
benchmark-specific implementation is isolated here. There are no copied or
linked production packages under `source/`. Runtime imports resolve directly to
the original StreamMeCo, Mandol, TST, and consolidation roots beside this
benchmark. The superseded package trees remain under
`metadata/upstreamed_source_packages_20260918/` as inactive provenance.

Reusable online behavior now belongs to the original systems. M3 owns the
CAM++/TST assignment contract and pre-mutation evidence, content-addressed ASR
reuse, exact media boundaries, consolidation evidence export, durable graph
transactions, immutable cutoff snapshots, configurable compression, and exact
Mandol clip intervals. Mandol owns the 302 reranking transport and its hybrid
retriever integration. The benchmark owns only interface calls, C1-C4
construction and assertions, Jake/AEA schedules and question manifests,
exact-choice accuracy calculation, reports, validation gates, and launch
control.
`consolidation.port.attach_online` and `consolidate_until` remain the public
maintenance interface. Benchmark files and directly used production
dependencies are fingerprinted separately and included in launch and resume
gates.
The primary model is official Responses `gpt-5.6-terra`, medium;
Terra also constructs video memories through the shared native
`mmagent.memory_backend` interface. Its implementation lives in the original
`StreamMeCo/mmagent/memory_processing_terra.py`, imported directly from the
production package.
It sends frames sampled at 2 fps plus existing face/voice evidence, with one
structured JSON request per construction. Exact requests (content-addressed image
references), images, raw responses and usage are retained in `cache/terra_construction`.
The superseded Qwen run stays in `results/`; the corrected run uses `results_terra/`.
consolidation uses the existing official `propose_official` with `gpt-5.6-sol`, high.
The directory name is retained for artifact continuity; it does not select models.

The scheduler uses integer microseconds. Source-relative clips are at most 30
seconds and are split at every QA, source, 300-second, 1,200-second,
and 3,600-second boundary. All C1–C4 observations commit before maintenance.
Consolidation and native reindexing finish before compression, hourly persistence,
and same-time questions. Failed consolidation stops execution. No completed graph
is filtered backwards to approximate an earlier query.

Each QA timestamp uses an immutable temporary graph, an exact SHA-256, one M3 export,
and one Mandol build. The isolated interchange schema adds explicit per-clip
intervals because the legacy fixed 30-second assumption does not describe split
online clips. Retrieval still uses the existing M3 search and Mandol adapter and
hybrid BM25/dense/SPLADE search. Relations and graph expansion are disabled. R2 uses BM25 + dense + SPLADE, RRF fusion, and `Qwen/Qwen3-Reranker-0.6B` through `https://api.302.ai/v1/rerank`. Reranking failure stops evaluation; it never silently falls back to the fused order. All indexes and the reranker transport initialize before the warm retrieval clock starts.
Missing component timings are reported as missing, not zero. The final-answer
prompt and parameters are identical across R1 and R2 except evidence.

The Responses client disables automatic retries, times the first nonempty
`response.output_text.delta`, verifies the returned model, and retains request,
stream-event, completed-response, and token-usage records without credentials.
Checkpoint publication atomically advances a pointer to four independent graph
files. An intermediate checkpoint before QA preserves the exact state if answer
execution is interrupted. Config, source, model manifest, and event-plan changes
refuse resume. An interrupted answer POST without a durable completion receipt
fails closed rather than silently issuing a duplicate answer call.

### Online TST policy

TST replaces the speaker embedding frontend with SpeechBrain ECAPA at immutable
revision `0f99f2d0ebe89ac095bcc5903c4dd8f72b367286`. It uses a separate audio/ECAPA
cache and no prior enrollment, named identities, or frozen gallery. Each graph
starts empty. The unchanged native `VideoGraph.search_voice_nodes`, `update_node`,
and `add_voice_node` implement mean pairwise cosine matching at 0.6, update the
best accepted node, or create a new voice node below threshold. The native cap
of 20 retained embeddings is unchanged. TST's 4-second/1.5-second sliding windows
supply 192-dimensional vectors to this policy. C1 stores only CAM++ vectors;
C2–C4 store only ECAPA vectors, with explicit encoder provenance. Graphs and
embedding histories remain independent, including after checkpoint reload.

Earlier frozen-enrollment calibration artifacts are retained as superseded
preparation under `tst_assets/` and `metadata/superseded_frozen_enrollment/`.
They are not inputs, threshold sources, or exclusions for the requested run.

The isolated Deepgram request uses `diarize_model=v2` alone; combining it with
`diarize=true` is rejected by the API. See the
[official diarization contract](https://developers.deepgram.com/docs/diarization).

### Preserved caches and disk policy

The original 646 Jake videos remain at `/opt/streammeco/data/egolife_day1`. The 182 additional original Day 1 recordings are under this run’s `media/jake/`, pinned and checksum-verified against `lmms-lab/EgoLife`. AEA remains at `/opt/streammeco/aea_6h`. Authorized cleanup removed old derived split videos and
pip downloads; `metadata/storage_cleanup.json` records exact removed paths.

This run retains content-bound ASR caches, encoder model provenance,
ECAPA query WAVs and embeddings, per-clip construction/VLM audits, five-minute graphs,
Mandol indexes, retrieved evidence, and raw API responses. Only
short-lived decoded/split media and superseded restart checkpoints are removed.
Temporary media is scoped to one segment; the runtime stops below 1 GiB free.
Durable graph snapshots occur every 300 media seconds; hourly graph paths link to
these snapshots. Temporary QA graphs expire after both retrieval paths succeed.
Crash-recovery transactions persist until superseded. Mandol export, adapter/index build, dense encoding, and index reload/warmup have a separate construction timing category, sampled once per snapshot and excluded from warm retrieval. A backend-only comparison can reuse
all saved evidence without reconstructing the graph or invoking retrieval:

```bash
# Supply official OPENAI_API_KEY through the private environment, not this folder.
/opt/streammeco/.venv/bin/python scripts/reanswer_cached.py \
  --model <requested-official-model> \
  --output reanswers/<comparison-id>
```

Those comparison timings cover the new streamed answer only. They do not claim
fresh retrieval latency.

### Verification and launch

`--validate-prefix` runs deterministic clock, snapshot, checkpoint, call-count,
streaming, and remote graph/mapper tests. GPU smoke artifacts live under `smoke/`.
The maintenance smoke uses an actual GPU-constructed prefix plus explicitly
synthetic missing-media intervals at 20/40/60 minutes; it validates real Sol
patch application and native reindexing, not one hour of media understanding.
Preflight verifies artifact contents, hashes, all media/model paths, real CUDA,
imports in both venvs, credentials by presence, official model access, and disk.
`launch_gate.py` requires inspected smoke receipts and validated source hashes.

Updated consolidation uses the existing local MOSS checkpoint and inference runner
configured in `configs/moss.json`. Its window builder receives exact
source paths, offsets, and gaps from the committed benchmark plan. Voice candidate
scores are recorded before mutation in each clip audit and fetched into the shared
worker through a cutoff-specific assignment log. Missing scores fail closed.
Preflight also performs a minimal real embedding request to detect exhausted API
credits, which model-list access alone cannot detect.

The full launcher creates a unique tmux session with a unique durable log,
status, and exit-status file. A live session means **running**, never completed.
Only a zero exit status plus verified `results/COMPLETE.json` and expected outputs
can support completion. This task's end state is verified launch, not completion.
