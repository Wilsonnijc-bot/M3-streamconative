# Handoff: repeat Jake DAY1 first-10 benchmark with local GPU Qwen3.5

Continue the existing EgoLife/M3 experiment. Implement and run the same first-ten-question, four-method benchmark, replacing **all Gemini LLM/VLM reasoning with local GPU Qwen3.5**. Reuse the existing code, data, preprocessing, retrieval dependencies, instrumentation and tests wherever valid. Do not build a new benchmark from scratch.

This is a new model condition, not permission to alter or erase the Gemini experiment. Finish the actual run, verify its artifacts, and copy results to the Mac. Do not stop at implementation or preflight.

## 1. Experimental contract

- Jake DAY1 only; the same first ten EgoLifeQA questions in chronological order.
- Same source clips, query timestamps, clip boundaries, prompts, memory schema, graph update rules, top-k, thresholds, compression parameters and controller step limit as the current Gemini benchmark, unless a necessary Qwen-specific change is explicitly recorded.
- **144 processing segments from 136 source clips**, including splits at query timestamps. Verify the current planner instead of hardcoding this count.
- One chronological **Qwen-built** M3 memory stream, with Q1–Q10 snapshots containing no information after each question's timestamp.
- Four methods share those exact Qwen-built snapshots:
  - **A:** uncompressed M3 + StreamMeCo, normal controller.
  - **B:** uncompressed M3 + StreamMeCo, one retrieval request and one answer call.
  - **C:** independently compress each query-time snapshot, then one retrieval request and one answer call.
  - **D:** existing Mandol adaptor on that question's uncompressed snapshot, one hybrid retrieval request and one answer call.
- Exactly **40 actual predictions**, not the obsolete 80-trial dual-backend configuration.
- All memory reasoning, controller reasoning, any query generation, final answers and any reasoning-based repair use **local Qwen only**. No Gemini or other LLM fallback.
- Existing ASR services, embedding services, reranker and algorithmic retrieval stay unchanged. These are distinct from the reasoning backend.

## 2. FPS: make the comparison explicit

Expose VLM sampling FPS as a run-level setting and save its effective value and actual frame counts.

- **Default: 2 FPS**, preserving the Gemini comparison's sampling. This is the model-only comparison.
- **Optional: 1 FPS** if subsequently selected by the user, or if necessary to make Qwen viable after a documented 2-FPS preflight failure. Label it explicitly as **Qwen + 1 FPS**, a change in both backend and visual sampling; do not describe it as model-only.
- Changing VLM FPS does not automatically change the existing **5-FPS face/preprocessing sampling**, clip durations, or audio. Keep these distinct.
- Verify the frames actually submitted to Qwen; do not merely change a config field that the processor ignores.
- Never combine memories from different FPS/generation configurations in one resumed state.

Do not automatically run both FPS conditions. Start with the controlled 2-FPS condition. If 1 FPS is selected, use a separate manifest and result root.

## 3. Infrastructure and isolation

```text
Hyperstack instance: 1042997
Host: ubuntu@185.216.21.158
GPU: NVIDIA RTX A6000
SSH key: /Users/nijiachen/.ssh/streammeco_hyperstack_1042997
Original key: /Users/nijiachen/Downloads/njc_Hyperstack (1).txt

Existing Gemini tmux: egolife_10q
New, separate Qwen tmux: egolife_10q_qwen
Remote code root: /opt/streammeco/run
StreamMeCo: /opt/streammeco/run/StreamMeCo
Mandol: /opt/streammeco/run/Mandol
StreamMeCo Python: /opt/streammeco/.venv/bin/python
Mandol Python: /opt/streammeco/mandol-venv/bin/python
Local Qwen checkpoint: /opt/streammeco/models/Qwen3.5-4B
Secrets environment: /opt/streammeco/secrets/runtime.env
QA: /opt/streammeco/data/EgoLifeQA_A1_JAKE.json
Clips: /opt/streammeco/data/egolife_day1

Mac repository: /Users/nijiachen/StreamMeCo
```

Use the installed **Qwen/Qwen3.5-4B** checkpoint unless the user explicitly selects another size. Print/save the actual checkpoint, revision/hash where available, dtype, device, generation settings and FPS. Do not silently substitute a different Qwen model.

At handoff creation, the Gemini pipeline was running, with at least **42 committed segments**. Recheck current state: this observation becomes stale. Some summary fields in `experiment_GPU_record.md` are stale; reconcile them against live logs/checkpoints rather than assuming the Gemini run is paused.

```text
Gemini run: /opt/streammeco/run/egolife_10q_gemini
Gemini status: .../pipeline_status.txt
Gemini log: .../pipeline.log
Gemini checkpoint: .../work/build_state.pkl
Gemini results: .../results
```

- Do not stop or contaminate a healthy Gemini run. Prepare Qwen code while it runs, and queue Qwen GPU preflights/full execution after Gemini relinquishes the GPU. Do not run competing experiments during latency measurement.
- Create/reuse one separate Qwen session named `egolife_10q_qwen`, with its own windows and durable logs. Keep the existing Gemini session `egolife_10q` untouched. Run all Qwen experiment work inside the Qwen session; do not launch duplicate Qwen experiments. Separate sessions do not isolate GPU resources, so wait for Gemini to relinquish the GPU before Qwen preflights/inference.
- Use separate run roots, e.g. `/opt/streammeco/run/egolife_10q_qwen35_4b_fps2` and Mac `egolife_m3_jake_day1/provenance/raw/qwen_non_thinking`.
- Make isolated copies/checkouts of the **actual current working code, including uncommitted/untracked implementation files**. A clean checkout of an old commit will lose this benchmark. Do not modify shared files that the still-running Gemini launcher will read in later phases. Reuse environments, model weights and data rather than duplicating them.
- Maintain the existing project GPU ledger. Record entrypoints, code hashes, manifests, exit statuses and actual results. Keep secrets out of logs/reports.

## 4. What to reuse and what to rebuild

**Reuse directly after provenance checks:**

- Original clips, QA selection and chronological boundary planner.
- Current benchmark, exporter, Mandol adaptor, compression and reporting implementations.
- Environments, installed weights, original SPLADE checkpoint and working API connections.
- Successful per-provider ASR caches from `egolife_10q_gemini/results/asr_cache/`. Cache identity includes audio bytes, provider and configuration. Copy/link compatible successful cache entries into the Qwen run; preserve the originals.
- Graph-independent preprocessing artifacts: exact audio, decoded media, face detections/features and speaker features, where their schema and sampling configuration match. Inspect caches before reuse.

**Do not reuse as Qwen outputs:**

- Gemini-generated episodic/semantic memories, graph state, snapshots, compression results, answers or retrieval results.
- Global face/voice/character/node IDs assigned in the Gemini graph. Qwen may create different numbers of text nodes; resolve identities chronologically in the new graph.
- Embeddings of different generated text. Reuse only if the exact text and embedding model/dimension/settings match and provenance is verified; do not invent a cache hit.
- Mandol indexes built from Gemini memories. Reuse the adaptor code, but adapt/re-embed the new Qwen snapshots.
- The old failed two-segment Qwen checkpoint by default: its generation settings and lineage are not the new condition. Start one fresh Qwen memory stream, then resume only that verified stream.

Cached preprocessing is allowed for executing this new run, but **cache hits are not fresh provider latency measurements**. Record cache-hit time separately and retain the original acquisition measurements/provenance. Separate observed cached-run throughput from an uncached-service estimate; do not report cached ASR as zero-cost service inference.

## 5. Preserve the separate retrieval stacks

| Methods | Embedding/retrieval stack |
| --- | --- |
| A/B/C | OpenRouter `openai/text-embedding-3-large`, 3072D; native M3 graph and StreamMeCo |
| D | 302.ai `Qwen/Qwen3-Embedding-0.6B`, 1024D; BM25 + local SPLADE; 302.ai `Qwen/Qwen3-Reranker-0.6B` |

Mandol must import text/metadata, **not M3 vectors**. The existing local directory `Mandol/naver/splade-v3` contains the original **`naver/splade-cocondenser-ensembledistil`** checkpoint; preserve and verify `egolife_checkpoint_source.json`. Do not replace it just because the directory name says v3.

Existing compression and the configured Mandol adaptation use zero reasoning calls; retain that behavior. If a new reasoning call is truly needed, it must use the local Qwen backend and be counted.

## 6. Reuse current acceleration defaults

- Deepgram and MAI run concurrently, with separately timed provider calls.
- Reuse HTTP clients/connections for remaining cloud services and local-server calls.
- Batch all episodic + semantic memory texts from **one clip** into one native embedding request. Keep each text/vector separate and preserve output-index ordering.
- Prepare **two upcoming segments** of decoding/ASR outside the graph. Preserve bounded queues; do not let future preprocessing mutate identity or memory state.
- Identity matching, Gemini-replacement Qwen reasoning, semantic integration and graph/checkpoint commits remain chronological.
- Join preparation workers before the retrieval benchmark. Do not measure query latency while construction work competes for resources.

## 7. Qwen backend work and the known previous failure

Relevant reusable files, relative to the current StreamMeCo repository:

```text
benchmarks/egolife_first10.py
benchmarks/gemini_runtime.py
benchmarks/gemini_report.py
benchmarks/qwen_text_server.py
benchmarks/segment_prefetch.py
benchmarks/segment_resilience.py
benchmarks/warm_query.py
cloud_http.py
m3_agent/memorization_memory_graphs.py
mmagent/memory_processing_gemini.py
mmagent/memory_processing_qwen.py
mmagent/utils/chat_qwen.py
mmagent/utils/chat_api.py
mmagent/utils/asr_resilience.py
```

Mandol entrypoint: `Mandol/benchmarks/egolife_m3_first10.py`.

Local run scripts/contracts: `gpu_setup/egolife_gemini/`, especially `MEASUREMENT.md`.

The current benchmark is deliberately Gemini-only: it sets `EGOLIFE_GEMINI_ONLY`, uses Gemini-only output mappings/runtime and validates Gemini model IDs. **Simply changing an environment variable is insufficient.** Add/refactor backend selection in the isolated Qwen copy, adapt manifests/output validation and clear only the Qwen run's Gemini-only guard. Preserve the active Gemini experiment's enforcement. Keep 40 Qwen trials, not a mixed 80-trial loop.

The old `qwen_text_server.py` is text-only. Reuse its structure/timing where appropriate, but memory generation needs multimodal support. Prefer a persistent, warmed Qwen instance serving both multimodal memory and text reasoning so the checkpoint is not loaded twice. Serialize GPU generation requests or use an explicit queue: the old threaded HTTP server has no generation lock. Keep model loading and warmup outside timed inference. Do not blindly retain per-call `torch.cuda.empty_cache()` if it defeats steady-state operation; measure and document the chosen behavior.

**Known blocker:** Qwen previously repeated events and truncated its memory JSON at segment 3. It sometimes omitted `high_level_conclusions`. Existing parser recovery and a Qwen text repair did not solve it reliably. Do not repeat the obsolete launch unchanged or declare success because the model loads.

Preflight both memory classes on the first three clips, particularly segment 3. Reuse robust parsing; use explicit schema instructions, adequate token budgets and, if needed, documented memory-only anti-repetition or structured decoding. Do not silently fabricate missing memory sections. Record any model-specific prompting/decoding change relative to Gemini. Do not blindly carry the old text server's 768-token limit into every purpose. Keep controller/answer behavior isolated from memory-only decoding fixes.

## 8. Warm query latency is mandatory

All A/B/C/D evaluation rows must measure **warm retrieval engines with an uncached actual question**.

- Load each snapshot and initialize its indexes/models before the trial timer.
- Run the existing fixed unrelated retrieval probe and discard its evidence.
- Save snapshot load, model load, startup warmup and probe timings separately.
- Never warm up with the actual QA question or reuse its answer/query embedding.
- Warm the persistent local Qwen model outside trial timing; do not count startup generation as a question/controller call.
- Actual timed query embedding, search, graph selection, fusion, reranking and Qwen reasoning remain included.
- A retains every controller round. B/C/D retain one actual question retrieval request and one answer call; warmup probes are separately classified setup operations.
- Cloud-provider internal model residency is not controlled; record actual service wall time.
- Do not retrospectively relabel the original cold preflight as warm by subtracting a number.

## 9. Exact timing and failure accounting

Reuse the current timing contract, adding local-GPU details:

- `time.perf_counter()` for elapsed time; wall-clock request start/end for tracing.
- Record server queue wait, processor/tokenization/media preparation, device transfer where measurable, CUDA-synchronized model generation, decoding, server response and client wall latency separately. Do not conflate the old helper's whole-call timing with pure GPU generation.
- Use CUDA synchronization around GPU timing where required. Record TTFT only if actually measured; otherwise unavailable, never invented.
- Log model ID, purpose, segment/question/method ID, input/output tokens, output caps, truncation, retries, FPS/frame count and generation settings.
- Whole embedding batch latency, input count, tokens and each API attempt. Per-text latency is unavailable, not batch latency divided by text count.
- Preparation work, consumer wait, ready-queue wait, ordered processing, admission-to-checkpoint latency and run throughput remain separate. Do not sum overlapping stages.
- Do not pool cached/uncached or old/new execution policies into an unlabeled latency average.

Continue the latest authorized failure policy:

- Two bounded ASR attempts per provider; retain the successful provider, or use video-only if both fail. Persist detailed failures and successful caches independently.
- On unrecoverable model/API/invalid-output failure for a segment, roll back partial graph mutations, persist a skipped-segment record/checkpoint, and advance. Extend the current Gemini-oriented failure classifier for Qwen errors rather than swallowing all exceptions.
- Skipped/degraded segments are explicit in snapshots and comparisons; all four methods share the same coverage gaps.
- Startup/checkpoint/configuration errors and programming bugs are not silently treated as missing observations. No alternate reasoning model fallback.
- The first-three-clip preflight must demonstrate successful Qwen construction, not pass merely by skipping every difficult segment.

## 10. Execution and required artifacts

1. Inspect current Gemini status and working code; isolate the new Qwen condition.
2. Verify checkpoint, environments, CUDA and compatible reusable caches.
3. Test backend routing, structured Qwen memory on clips 1–3, all four retrieval paths, warm-up exclusion, batch ordering, prefetched chronology, rollback and failure continuation.
4. Start the one persistent Qwen experiment in the separate `egolife_10q_qwen` tmux session, with a launch lock, explicit environment and durable exit status. Use `tmux new-session -A -s egolife_10q_qwen` to create or attach to it.
5. Build one Qwen memory stream; save all ten snapshots; compress each independently; adapt each to Mandol; produce 40 predictions.
6. Monitor actual checkpoints, failures and logs. Estimate ETA from observed checkpoint throughput, not summed overlapping stage latency or the Gemini processing rate.
7. Validate lineage, chronological coverage/gaps, 40-row uniqueness, one-shot counts, Qwen-only reasoning, warmed retrieval engines, readable artifacts and final status.
8. Copy artifacts/logs to the separate Mac destination. The existing Gemini sync watcher targets the Gemini run only; configure a separate transfer watcher for the Qwen root, without running inference on the Mac.

Required artifacts include:

```text
model/config/FPS manifest + execution policies + code hashes
memory/q01_uncompressed ... q10_uncompressed
streammeco_compressed/q01 ... q10
mandol/adapted_snapshots + original-M3-ID mapping
method_A_normal_streammeco.jsonl
method_B_streammeco_oneshot.jsonl
method_C_compressed_oneshot.jsonl
method_D_mandol.jsonl
qwen_calls.jsonl
asr_calls.jsonl + compatible cache provenance
embedding_batch_calls.jsonl
memory_construction_latency.jsonl
segment_schedule_events.jsonl
api/model failure and skipped-segment records
retrieval_warmup.jsonl
detailed_retrieval_events.jsonl
compression/adaptation metrics
comparison.csv + comparison.md + aggregate_metrics.json
validation.json + durable logs/exit status
```

The comparison must include per-question/per-method memory size, coverage gaps, actual retrieval count, Qwen-call count, embedding/dense/sparse/scoring/fusion/lookup/reranking/total retrieval latency, Qwen reasoning latency, warm question-to-answer latency, prediction and correctness. Report accuracy /10, mean/median/P95 retrieval latency, mean/median QA latency, mean embedding/model latency and mean call/query counts. Clearly distinguish the 2-FPS model-only comparison from any separately selected 1-FPS condition.

Start by reporting what is reusable, the isolated run paths, effective Qwen model/FPS, and the current Gemini status. Then execute the authorized work without asking for repeated permission.

## Updated local result contract

Use `egolife_m3_jake_day1/results/qwen_thinking/` for the intended thinking-mode 10-QA benchmark’s human-readable Markdown; preserve its raw files in `provenance/raw/qwen_thinking/`. Gemini’s full run is `results/gemini/`. Keep first-clip comparisons, preflight and other short diagnostics under `smoke_tests/`. Group executable scripts in `scripts/`, reusable data in typed `cache/{asr,faces,voices,media,graphs,dependencies}/` folders, and small QA references in `provenance/reference_data/`; do not recreate an inputs folder or flat top-level run directories. Remote run paths do not change. Use `scripts/sync_run.py` and `scripts/render_results.py` to preserve this layout.

Follow [the current result contract](../../RESULT_CONTRACT.md) when exporting. Every run includes `vlm_outputs/README.md` and per-clip Markdown with generated descriptions, exact final text, attempts and commit status; this is separate from committed memory and retrieval evidence. Preserve exact backend responses in provenance.
