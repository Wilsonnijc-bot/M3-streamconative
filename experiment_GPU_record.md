# GPU Experiment Record

## Jake Day 1 first-ten M3/StreamMeCo/Mandol benchmark - 2026-09-14

- **Status:** running
- **Provider:** Hyperstack hosted GPU plus 302.ai and OpenRouter APIs
- **Instance/container ID:** Hyperstack VM `1042997`
- **Purpose:** Construct one chronological, leak-free M3 memory through the first ten Jake Day 1 questions, save ten query-time snapshots, and compare StreamMeCo normal-controller, StreamMeCo one-shot, compressed StreamMeCo one-shot, and Mandol-adapted one-shot retrieval with both Qwen 3.5 4B and Gemini 3.8 Flash answer backends.
- **Method:** Process Jake's approximately 30-second Day 1 clips once through Qwen-based M3 construction; checkpoint the same graph lineage at each query time; compress each snapshot independently; adapt each uncompressed snapshot through the embedding-free M3/Mandol contract; build Mandol vectors with 302.ai `Qwen/Qwen3-Embedding-0.6B`; rerank Mandol candidates with 302.ai `Qwen/Qwen3-Reranker-0.6B`; and complete 80 QA evaluations with detailed component timing and retrieved-evidence records.
- **Key dependencies:** Hyperstack `n3-RTX-A6000x1`; Ubuntu Server 22.04 LTS R550 CUDA 12.4; NVIDIA RTX A6000; StreamMeCo source revision `72575bfcf955ddc35d094aea040d083697b735f0` plus the current benchmark/exporter changes; Mandol revision `6d7af4f004e1b311fb5c93d3e14fab90677942d8` plus the M3 adaptor changes; local `Qwen/Qwen3.5-4B`; Gemini `gemini-3.8-flash`; OpenRouter `openai/text-embedding-3-large`; 302.ai Qwen embedding and reranking.
- **Results:** pending
- **Artifacts:** Remote root: `/opt/streammeco/run/egolife_10q`; master log: `/opt/streammeco/run/logs/egolife_10q_master.log`; tmux session: `egolife_10q`; local target: `egolife_m3_jake_day1/egolife_10q_20260914`.
- **Notes:** All experiment execution is confined to the single `egolife_10q` tmux session. The runner checkpoints after every source segment and refuses final completion unless all 80 QA rows and all required snapshot, compression, Mandol, latency, and comparison artifacts validate.

## Jake Day 1 first-five M3/StreamMeCo benchmark - 2026-09-13

- **Status:** cancelled
- **Provider:** AutoDL / SeetaCloud hosted GPU
- **Instance/container ID:** autodl-container-ae124db9f3-5c709e43
- **Purpose:** Build one chronological, leak-free M3 memory through the first five Jake Day 1 questions and compare normal controller retrieval, uncompressed one-shot retrieval, and compressed one-shot retrieval.
- **Method:** Process 95 chronological source clips through five exact query-time boundaries once; save five uncompressed snapshots; compress each snapshot independently with StreamMeCo; answer all five questions with all three retrieval modes and record decomposed latency.
- **Key dependencies:** NVIDIA RTX 4090; PyTorch 2.6.0+cu124; base source revision `67c8e8c74c97e69f625890936754a9f934f3d35a`; adapter patch SHA-256 `f4eb70c9e002f795fd4fa3d31f7c4757fad76e1f3d4e52b3962c4121d9261bed`; Qwen/Qwen3.5-4B; SpeakerLab CAM++; InsightFace Buffalo-L; Deepgram Nova-3; OpenRouter `microsoft/mai-transcribe-2`.
- **Results:** Cancelled by user during the first 17.6-second clip before any `build_state.pkl` memory checkpoint was written.
- **Artifacts:** Remote: `/root/autodl-tmp/identity-stack/runs/streammeco-first5/results`; local target: `egolife_m3_jake_day1/results`; log: `/root/autodl-tmp/identity-stack/runs/streammeco-first5/logs/first5-benchmark.log`; tmux session: `streammeco-first5-20260913`.
- **Notes:** Qwen 3.5 4B, CAM++, Buffalo-L, Deepgram, and MAI-Transcribe preflights passed. The run was explicitly stopped on 2026-09-14; its partial log and cached face/voice intermediates were preserved. Gold answer, target time, keywords, and reason fields are excluded from inference inputs and used only after prediction for exact-letter scoring.


## Gemini 3.8 vs Qwen 3.5 4B first-clip comparison - 2026-09-14

- **Status:** completed
- **Provider:** AutoDL / SeetaCloud hosted GPU plus 302.ai hosted Gemini API
- **Instance/container ID:** autodl-container-ae124db9f3-5c709e43
- **Purpose:** Compare first-clip memory construction from local Qwen 3.5 4B and Gemini 3.8 Flash while measuring every shared preprocessing stage, each VLM branch, text embedding, graph update, and clip-to-VideoGraph wall time.
- **Method:** Freshly decode the 17.6-second Jake Day 1 clip and run both mandatory ASR services, CAM++ speaker embedding, and Buffalo-L face detection/recognition once. From the same resulting context, start Qwen 3.5 4B on the RTX 4090 and a GPU-originated direct 302.ai `gemini-3.8-flash` request concurrently, then independently embed each model's episodic and semantic memories through OpenRouter `openai/text-embedding-3-large` and update cloned VideoGraphs. The Gemini comparison uses the diagnostic direct-IP/Host-header route with TLS certificate verification disabled because normal GPU-host DNS/TLS egress is unavailable; it is not a production transport.
- **Key dependencies:** PyTorch 2.6.0+cu124; NVIDIA RTX 4090; local `Qwen/Qwen3.5-4B` with native thinking enabled; Gemini `gemini-3.8-flash` via 302.ai; SpeakerLab CAM++; InsightFace Buffalo-L; Deepgram Nova-3; OpenRouter `microsoft/mai-transcribe-2`; OpenRouter `openai/text-embedding-3-large` embeddings. FLA imported successfully; `causal_conv1d` was unavailable because its installed extension was ABI-incompatible with PyTorch 2.6.0+cu124, so Qwen used the reference PyTorch fallback.
- **Results:** OpenRouter embedding preflight returned one 3,072-dimensional vector in 2,092.71 ms. Shared preprocessing took 21,720.25 ms. Qwen: VLM 107,613.76 ms, text embedding 3,834.57 ms, clip-to-graph 133,169.57 ms, 11 nodes/0 edges. Gemini: VLM 25,485.34 ms, text embedding 4,799.15 ms, clip-to-graph 52,006.62 ms, 10 nodes/1 edge. Buffalo-L detected 152 candidates but produced zero qualified face identities under current thresholds.
- **Artifacts:** Remote results: `/root/autodl-tmp/identity-stack/runs/streammeco-first5/results/first_clip_vlm_compare_openrouter_20260914`; remote work: `/root/autodl-tmp/identity-stack/runs/streammeco-first5/work/first_clip_vlm_compare_openrouter_20260914`; log: `/root/autodl-tmp/identity-stack/runs/streammeco-first5/logs/first-clip-vlm-compare-openrouter-20260914.log`; local copy: `egolife_m3_jake_day1/first_clip_vlm_compare_openrouter_20260914`; tmux session: `first-clip-vlm-compare-openrouter-20260914`.
- **Notes:** FLA imported successfully. `causal_conv1d` remained ABI-incompatible with PyTorch 2.6.0+cu124, so Qwen used the correct slower reference PyTorch implementation; Qwen latency is not an optimized-kernel result.


## Hyperstack Gemini 3.8 vs Qwen 3.5 4B first-clip comparison - 2026-09-14

- **Status:** completed
- **Provider:** Hyperstack hosted GPU plus 302.ai hosted Gemini API
- **Instance/container ID:** Hyperstack VM `1042997`
- **Purpose:** Reproduce the first-clip Gemini 3.8 Flash versus local Qwen 3.5 4B memory-construction comparison on the prepared Hyperstack RTX A6000 environment.
- **Method:** Decode `DAY1_A1_JAKE_11094208.mp4`; run Deepgram and MAI-Transcribe-2 ASR, CAM++ speaker embedding, and Buffalo-L face processing once; execute local Qwen 3.5 4B and 302.ai `gemini-3.8-flash` branches concurrently; embed both memory outputs with OpenRouter `openai/text-embedding-3-large`; and construct independent VideoGraphs.
- **Key dependencies:** Hyperstack `n3-RTX-A6000x1`; Ubuntu Server 22.04 LTS R550 CUDA 12.4; NVIDIA RTX A6000; PyTorch 2.6.0+cu124; source revision `72575bfcf955ddc35d094aea040d083697b735f0`; Qwen/Qwen3.5-4B; SpeakerLab CAM++; InsightFace Buffalo-L; Deepgram Nova-3; OpenRouter `microsoft/mai-transcribe-2`; OpenRouter `openai/text-embedding-3-large`; Gemini `gemini-3.8-flash` via 302.ai.
- **Results:** Attempt 3 completed with exit status `0`. Shared preprocessing: 18,545.20 ms; 89 frames, 2 voice identities, 0 face identities. Qwen: valid on generation attempt 1, 1,843 output tokens of a 3,072-token cap, VLM 111,703.85 ms, text embedding 1,059.59 ms, clip-to-graph 131,310.04 ms, 5 episodic + 3 semantic memories, 10 nodes/0 edges. Gemini: VLM 12,124.97 ms, text embedding 1,666.47 ms, clip-to-graph 32,339.18 ms, 6 episodic + 2 semantic memories, 10 nodes/3 edges. Buffalo-L found 152 raw candidates and 0 qualified identities.
- **Artifacts:** Successful remote results/work/log: `/opt/streammeco/run/results/first-clip-vlm-compare-hyperstack-20260914T052138Z`, `/opt/streammeco/run/work/first-clip-vlm-compare-hyperstack-20260914T052138Z`, `/opt/streammeco/run/logs/first-clip-vlm-compare-hyperstack-20260914T052138Z.log`; local result root: `egolife_m3_jake_day1/first_clip_vlm_compare_hyperstack_20260914T052138Z`; successful tmux session: `first-clip-vlm-compare-hyperstack-20260914T052138Z`. Failed-attempt logs are retained under the local `provenance/` folder and at their original remote paths.
- **Notes:** Attempt 1 failed under the legacy one-shot parser and produced no result artifacts or exit file. Attempt 2 exited `1` before VLM execution because the launcher used `CAMPLUS_MODEL_PATH` instead of the runbook/code variable `CAMPLUS_CHECKPOINT`; it confirmed the corrected exit wrapper. Attempt 3 used the verified CAM++ path and the corrected parser, which retains raw/post-thinking diagnostics, accepts documented JSON/Python-dict key variants, requires nonempty string lists for both memory classes, and retries invalid generations. Benchmark SHA-256: `5967d99787f22b8f4912db867eacad261d8466db244b44354ddb9c8c0153d42f`; Qwen caller SHA-256: `3696ca3f5677ac36ef4a53817c09f277fa57515b28bd9f780ee14eb2c972496e`. Artifact JSON and pickle readability, graph counts, fatal-log scan, exit status, and remote-to-local transfer were verified.

## EgoLife first-10 Gemini-only shared memory — 2026-09-14

- **Status:** completed. All 144 segments, ten snapshots and 40 QA trials verified. Report-only repair completed successfully; final artifacts synced to the grouped Mac result folder.
- **Provider / instance:** Hyperstack, instance `1042997`, RTX A6000; SSH `ubuntu@185.216.21.158`.
- **Purpose:** Replace failed Qwen reasoning with cloud `gemini-3.8-flash` through 302.ai; 10 chronological Jake DAY1 questions × A/B/C/D = 40 predictions.
- **Method:** One fresh Gemini memory build; A normal controller; B native one-shot; C independently compressed snapshots one-shot; D existing Mandol adaptor, one hybrid request and final answer. The two Qwen segments remain archived and are not reused.
- **Dependencies:** StreamMeCo `/opt/streammeco/.venv`, native `openai/text-embedding-3-large` through OpenRouter; Mandol `/opt/streammeco/mandol-venv`, 302.ai `Qwen/Qwen3-Embedding-0.6B` (1024 dimensions), `Qwen/Qwen3-Reranker-0.6B`, original `naver/splade-cocondenser-ensembledistil` plus BM25. M3 embeddings are excluded from Mandol export. Existing ASR/face/speaker preprocessing retained.
- **Execution:** Existing single tmux session `egolife_10q`, window `gemini-pipeline`. Remote scripts `/opt/streammeco/run/egolife_10q_gemini/`; local reproducible scripts `gpu_setup/egolife_gemini/`.
- **Preflight evidence:** CUDA tensor check passed (`torch 2.6.0+cu124`, RTX A6000). Live endpoint returned exact requested model identifier `gemini-3.8-flash` and `OK`. Three Gemini memory segments committed. A/B/C/D live retrieval and final-answer preflights passed; A made 4 retrieval requests/6 Gemini calls, B/C/D each 1/1. Mandol lazy dense loading bug fixed and separate dense/lookup/fusion timing retested. Focused suite: 26 passed; cross-repository acceptance: 1 passed; report/lineage guard: 1 passed.
- **Artifacts:** Remote `/opt/streammeco/run/egolife_10q_gemini/results`, separate `/smoke/results`; durable `preflight.log`, planned `pipeline.log`; Mac destination `egolife_m3_jake_day1/egolife_10q_gemini_20260914`.
- **Results:** Full benchmark pending; no production predictions yet. Three-clip preflight memories and selected evidence exported separately to `egolife_m3_jake_day1/gemini_preflight_review_20260914/`. A/B/C/D end-to-end preflight: 65.412/11.856/11.505/29.070 seconds (D selected detailed-timing retest). These are functional smoke trials with incomplete Q1 memory, not accuracy estimates. No local inference or alternate reasoning fallback permitted.

- **Transfer orchestration:** Mac-only watcher `gpu_setup/egolife_gemini/watch_and_sync.sh` polls remote status and copies final artifacts on exit; it runs no inference. Review folder: `egolife_m3_jake_day1/gemini_preflight_review_20260914/`, 55 file hashes verified and all Markdown links resolved.

- **ASR incident and repair:** MAI failed twice on segment 7; Deepgram returned successfully but its response was lost when the combined step failed. Old logging suppressed the root error. Added durable per-provider/audio/config success caches, observable HTTP/transport errors with credential redaction, up to five retries for transient network/408/429/5xx failures, and immediate failure for permanent errors. Retesting clip 7 in the same tmux session before resuming the full pipeline; no provider substitution.

- **Live ASR repair evidence:** Clip 7 Deepgram succeeded in 919.95 ms with 0 normalized segments. MAI attempt 1 returned HTTP 408 (`Provider returned 408`) after 120,675.25 ms; attempt 2 succeeded in 940.53 ms with 1 segment after a 2-second backoff. Both successes are cached independently. Four resilience tests passed; clip 7 continued to Gemini construction. The captured timeout is from the repair attempt; the original failed run did not retain its underlying error.

- **User-authorized continuation policy:** On ASR failure, retry at most twice, retain available provider output, and proceed video-only if neither succeeds. On unrecoverable cloud API failure in memory construction, restore the pre-segment graph, durably mark the segment skipped, checkpoint the chronology, and advance. All methods share the same gaps; snapshot metadata and comparison columns expose skipped/ASR-degraded segments. Native embedding retries bounded to two. Programming/configuration errors are not hidden. Seven continuation/cache/rollback tests passed. Paused the old process to apply this policy; committed memory retained.

- **Authorized acceleration:** Concurrent Deepgram/MAI by default; persistent HTTP pools (with actual TCP/TLS event counters); one whole-clip memory-text embedding batch; two-segment decode/ASR lookahead outside the graph. Identity matching, memory reasoning and commits remain chronological. Added per-call/per-batch metrics, preparation/queue/ordered/checkpoint timing and execution-policy boundaries. Sixteen focused tests passed; two-segment live measurement check in progress. Latency definitions documented in `gpu_setup/egolife_gemini/MEASUREMENT.md`.

- **Live optimized measurements passed:** Policy begins at segment 27. Segment 28 concurrent ASR provider wall times: Deepgram 545.71 ms, MAI 1,073.02 ms, combined stage 1,092.42 ms. Clip 27/28 nine-text embedding batches: 869.09/501.64 ms. Gemini clip 28 reused the HTTP connection (0 TCP connects, 0 TLS handshakes). Segment 28 ready-queue wait: 23,496.51 ms; admission-to-checkpoint: 111,995.28 ms; ordered stage: 79,818.44 ms. Full run resumed `2026-09-14T16:54:51Z` from 28 committed segments, with Q1 snapshot preserved. These measurements are not pooled with the earlier serial preflight.

- **Warm retrieval requested:** All upcoming A/B/C/D trials now warm loaded snapshots with a fixed non-benchmark retrieval probe, discard its evidence, then time an uncached actual question. Snapshot load and warmup are retained in `retrieval_warmup.jsonl`, excluded from QA counts/latencies. Actual embedding/search/fusion/reranking/API costs remain included. Final validator requires warm trial markers and warmed Mandol engines. Existing cold preflight artifacts unchanged; construction continues without restart.

## Jake DAY1 first-ten — isolated Qwen3.5-4B, 2 FPS — 2026-09-14

- **Status:** cancelled/superseded at user request: thinking must be enabled. This preserved run used thinking off. Concurrent execution was explicitly authorized by the user after initial queueing. Gemini remains active; both conditions may have GPU-contention latency.
- **Provider / instance:** Hyperstack / `1042997`, NVIDIA RTX A6000.
- **Purpose:** Same first ten chronological questions, four methods, 40 predictions; Qwen alone constructs shared M3 memories and performs all controller/answer reasoning.
- **Condition:** `/opt/streammeco/models/Qwen3.5-4B`, explicit 2-FPS timestamped JPEG sampling; face preprocessing remains 5 FPS. Persistent serialized local server, greedy non-thinking generation, 8192-token caps, memory-only repetition penalty 1.08. No reasoning fallback. Observed startup: bfloat16 on cuda:0; checkpoint hashes saved in checkpoint_hashes.sha256. Persistent Qwen server warmed successfully.
- **Isolation:** Actual remote working copies (including uncommitted code) copied into `/opt/streammeco/run/egolife_10q_qwen35_4b_fps2/code/{StreamMeCo,Mandol}`. Original Gemini code and session untouched. Native/Mandol retrieval stacks retained. Only compatible successful ASR caches and exact cut media reused; new graph identities, memories, compressed snapshots and Mandol indexes.
- **Entrypoint:** `bash /opt/streammeco/run/egolife_10q_qwen35_4b_fps2/launch_queued.sh`, tmux `egolife_10q_qwen`, launch lock, first-three-segment construction plus four-method preflight before full pipeline.
- **Artifacts:** Remote `/opt/streammeco/run/egolife_10q_qwen35_4b_fps2`; Mac `egolife_m3_jake_day1/egolife_10q_qwen35_4b_fps2_20260914`. Concurrent-start entrypoint no longer waits for Gemini. Durable `queue.log`, `server.log`, `preflight.log`, `pipeline.log`, launcher/pipeline statuses; separate Mac sync watcher.
- **Results:** Pending. Concurrent start confirmed 2026-09-14 17:29 UTC: Gemini GPU process and Qwen GPU server both resident; Qwen preflight streaming/preparing segments 1–3. 22 CPU tests passed; 119 compatible ASR caches copied. No Qwen accuracy, throughput or completion claimed. Gemini live evidence at inspection: status running, committed segment 57 (later status must be checked live); old ledger pause/segment estimates are stale.


## Jake DAY1 first-ten — Qwen3.5-4B, 2 FPS, thinking enabled — 2026-09-14

- **Status:** running startup and first-three-segment preflight.
- **Provider / instance:** Hyperstack / `1042997`, RTX A6000; concurrent with the existing Gemini worker as explicitly authorized.
- **Purpose:** Same 144-segment/136-clip chronological benchmark and 40 predictions, with local Qwen as the sole reasoning backend and thinking enabled for memory, controller and answer calls.
- **Condition:** Installed Qwen3.5-4B, bfloat16 CUDA, 2 FPS VLM / 5 FPS face preprocessing; `enable_thinking=True`, 16,384 generated-token cap, greedy decoding, memory-only repetition penalty 1.08. Thinking completion and submitted/processed frame counts checked in preflight. Generated thinking is removed before memory/answer parsing.
- **Isolation:** Fresh graph/work/results under `/opt/streammeco/run/egolife_10q_qwen35_4b_fps2_thinking`; prior thinking-off outputs are preserved and excluded. Code, environments, checkpoint, compatible ASR caches and exact cut media reused.
- **Entrypoint/session:** `launch_queued.sh` in that run root; tmux `egolife_10q_qwen:pipeline`, no wait for Gemini. Separate locks, durable logs and exit statuses.
- **Artifacts:** Remote root above; Mac `egolife_m3_jake_day1/egolife_10q_qwen35_4b_fps2_thinking_20260914` with dedicated sync watcher.
- **Results:** Thinking-enabled segment 1 passed: 36 frames, 5,142 generated tokens, 233,246 ms synchronized generation; complete thinking and valid JSON with 5 episodic + 3 semantic entries, committed without truncation/OOM. Segments 2–3 and retrieval preflight remain pending. Planner verified 144 segments/136 source clips. GPU contention may affect both runs' latency.

## Jake DAY1 two-segment Qwen identity prompt refinement — 2026-09-14

- **Status:** failed identity acceptance check; both inference segments completed.
- **Provider / instance:** Hyperstack / `1042997`, RTX A6000; concurrent with the untouched Gemini pipeline.
- **Purpose:** Test whether a surgical Qwen-only system prompt restores supplied voice IDs, transcript coverage, and M3 speaker-memory edges.
- **Change:** Add `mmagent/qwen_memory_prompt.py` to the isolated Qwen copy and prepend its identity instructions as a system message. Shared base memory prompt, Gemini prompt, generation settings, 2-FPS sampling, and thinking remain unchanged. No output rewriting or inferred ID injection.
- **Condition:** Qwen3.5-4B, bfloat16, thinking on, 16,384-token cap; greedy decoding, memory repetition penalty 1.08. Fresh two-segment memory stream; successful ASR and graph-independent cut media reused.
- **Entrypoint/session:** `/opt/streammeco/run/egolife_10q_qwen35_4b_fps2_thinking_ids_v2/run_two_segments.sh`, tmux `egolife_10q_qwen:pipeline`. Previous Qwen preflight stopped and preserved to avoid competing Qwen streams.
- **Artifacts:** Remote root above; Mac `egolife_m3_jake_day1/egolife_10q_qwen35_4b_fps2_thinking_ids_v2_20260914`; `qwen_identity_system_prompt.md`, `code_hashes.sha256`, `pipeline.log`, `server_calls.jsonl`, `results/identity_validation.json`, `gemini_prompt_unchanged.txt`, durable launcher status.
- **Results:** Segment 1 retained voice_0/voice_1 and added 5 voice-memory edges; segment 2 retained voice_0 only in semantic text, adding 1 edge, and failed episodic speaker coverage. Both completed thinking at 2 FPS (36/60 frames; 3240/3011 tokens; 151.38/138.32 s GPU generation). Manual review also found MAI provider-label/person confusion and a timestamp mistranslation. Exit status 1 is the explicit failed validation; no full benchmark launched for this condition. Gemini prompt and adapter hashes verified unchanged. Readable Markdown exports all 20 generated entries without rewriting model text.

- **Storage contract:** Local outputs are grouped under `egolife_m3_jake_day1/{scripts,cache,results,smoke_tests,provenance}` with no `inputs` folder. Full runs are `results/gemini` and `results/qwen_thinking`; first-clip/preflight/other short diagnostics are under `smoke_tests`. Human-readable memories, snapshot views, detailed latency and retrieval Markdown are generated from preserved raw JSON. Original checkpoints/logs are in `provenance/raw`; typed ASR/face/voice/media/graph caches are under `cache`. Sync/export defaults now target this structure; remote checkpoint paths are unchanged. All published Markdown links and 55 original preflight file hashes verified.
- **Segment 98 decode repair:** Pipeline stopped after segment 97 when MoviePy attempted to read beyond a 0.05-second encoded clip. For sub-second clips, audio extraction now uses FFmpeg directly and honors the nominal boundary duration. Actual failing clip regression passed: 1 video frame, 0.03 seconds audio (no extension past the QA boundary). Pipeline resumed `2026-09-14T18:20:16Z` from 97 committed segments.

- **Recovery confirmed:** Segment 98 subsequently encountered MAI HTTP 503 on both attempts, logged partial-ASR continuation, and committed successfully; Q5 snapshot saved. Segment 99 also committed by `2026-09-14T18:23:49Z`. Qwen thinking remains an intended full 10-QA benchmark under `results/qwen_thinking`, not a smoke-test category.

- **Per-clip outputs and explicit result contract:** Added `egolife_m3_jake_day1/RESULT_CONTRACT.md` and automatic per-clip VLM Markdown under each benchmark/smoke run. Views separate generated episodic/semantic output, exact final response, attempt history and commit state from integrated graph memory. Exact raw backend responses remain in `provenance/vlm_outputs/<run>`. Initial generation produced 119 per-clip views (105 Gemini and 3 Qwen thinking among them); all published links and selected response text were verified against source audits. Future syncs regenerate the views automatically.

## Jake DAY1 full Qwen thinking benchmark — identity prompt v2 — 2026-09-14

- **Status:** running; full tmux pipeline resumed from 2 verified committed segments.
- **Provider / instance:** Hyperstack / `1042997`, RTX A6000; user-authorized concurrent execution with Gemini.
- **Condition:** Installed Qwen3.5-4B, bfloat16, thinking on, 2-FPS VLM / 5-FPS face preprocessing, 16,384-token generation budget, same tested Qwen-only identity system prompt v2. Gemini prompt hashes remain unchanged.
- **Lineage:** Adopted the exact first two committed segment audits/checkpoint from `egolife_10q_qwen35_4b_fps2_thinking_ids_v2`; verified matching prompt, server, base prompt, model, FPS and completed thinking. Baseline-prompt memories are excluded. Source checkpoint hash and original timing provenance retained in `memory_resume_manifest.json` and `lineage/`.
- **Known quality limitations:** User authorized full evaluation after the mixed identity-prompt test. Missing episodic attribution and ASR provider-label confusion remain recorded findings; no output rewrite and no claim that identity validation passed.
- **Entrypoint / tmux:** `/opt/streammeco/run/egolife_10q_qwen35_4b_fps2_thinking_ids_v2_full/launch_full.sh`; `egolife_10q_qwen:pipeline`; locks and durable launcher/pipeline exit statuses. Actual startup 2026-09-14T18:34:35Z. 22 CPU checks passed before startup.
- **Phases:** Continue chronological build through all 10 query snapshots, independently compress, export/adapt Mandol, evaluate A/B/C/D, report and validate 40 predictions. Local server warmup and retrieval warmup remain outside QA timing. No additional smoke QA rows are counted as predictions.
- **Canonical artifacts:** `egolife_m3_jake_day1/results/qwen_thinking/README.md`; raw evidence in `provenance/raw/qwen_thinking`, runners in `scripts/`, typed caches under `cache/`. Old baseline-prompt artifacts preserved as `smoke_tests/qwen_thinking_baseline` / `provenance/raw/qwen_thinking_baseline` without mixing configurations.
- **Results:** Pending; launch log confirms `RESUME_BUILD completed_segments=2` and `PHASE_START memory_build`. Completion is not claimed before 40-row artifact validation.

- **Gemini final completion:** Memory construction completed at `2026-09-14T19:11:33Z`: 144/144 segments committed, 10 snapshots, no skipped memory segments, one recorded partial-ASR event. All 40 warm QA trials completed by `19:48:52Z`; accuracy A=4/10, B=4/10, C=6/10, D=3/10. Original report failed on a duplicate `round` dictionary keyword. Fixed exporter, added regression coverage, reran report/validation only; final validator passed with zero problems and finalization exit 0. Mean warm retrieval ms: A=1883.25, B=443.05, C=383.29, D=1667.11. Qwen full-run GPU work overlapped the QA period, so these are potentially contended warm timings, not isolated-load results.

## M3-Bench bedroom_01 — Gemini four-method benchmark — 2026-09-14

- **Status:** completed; 60 validated answers and exit 0.
- **Provider / instance:** Hyperstack / `1042997`, NVIDIA RTX A6000. EgoLife Qwen is independently active on the same GPU; contention is recorded.
- **Purpose:** Run the user's 15 open-ended bedroom_01 questions against A/B/C/D with warm retrieval measurements. This is separate from all EgoLife results.
- **Method:** One fresh chronological Gemini memory stream; source video 2163.264 seconds, 73 source clips / 76 processing segments after query-boundary cuts; 2 FPS VLM, 5 FPS face preprocessing, concurrent Deepgram/MAI, pooled HTTP, per-clip embedding batches, lookahead 2. Questions use per-question timestamp-limited graphs; see the revised schedule below. A normal controller; B uncompressed one-shot; C compressed one-shot; D independently adapted Mandol hybrid retrieval and reranking. User references withheld from memory/answer prompts; free-text semantic grading runs separately after all 60 answers.
- **Dependencies:** `gemini-3.8-flash` via 302.ai; A/B/C OpenRouter text-embedding-3-large (3072D). D Qwen3-Embedding-0.6B (1024D), original local SPLADE, BM25, Qwen3-Reranker-0.6B; no native-vector reuse. Verified PyTorch 2.6.0+cu124 CUDA tensor operation and imports of both dedicated entrypoints. Dedicated code snapshot preserves existing retrieval/controller/build/compression AST; open-ended/no-reference-leakage checks passed.
- **Entrypoint / tmux:** `/opt/streammeco/run/m3bench_bedroom_gemini/run_pipeline.sh`; `m3bench_bedroom_gemini`. Preparation, pipeline log and explicit exit status are persisted in that remote root. Separate code copies under `code/` protect both EgoLife runs.
- **Artifacts:** Remote `/opt/streammeco/run/m3bench_bedroom_gemini`; video `/opt/streammeco/data/m3bench_bedroom/bedroom_01.mp4`. Mac `m3bench_bedroom_01/{results/gemini,smoke_tests,cache,scripts,provenance}`; human-readable contract `m3bench_bedroom_01/RESULT_CONTRACT.md`.
- **Results:** Pending. Full launch is gated on a neutral first-segment A/B/C/D live preflight. The successful first segment is reused as the exact initial full-run checkpoint; smoke QA is isolated and excluded from benchmark scores/timing. Warmup uses an unrelated fixed probe; setup, adaptation, compression and semantic judging are excluded from query timing.

- **Verified startup:** 73 contiguous prepared clips cover all 2163.264 seconds; source SHA-256 matches Hugging Face LFS metadata. First committed segment used 60 VLM frames, yielded 7 episodic and 2 semantic entries; Gemini generation 20,472.99 ms, clip text-embedding batch 697.44 ms. A/B/C/D neutral functional checks each made one warm retrieval and returned non-empty free-text answers. Native dimension 3072 and Mandol 1024 plus all dense/BM25/SPLADE backends were verified. Auto-sync/exit verification runs as `com.streammeco.m3bench-bedroom-sync`; observed GPU load is recorded every 30 seconds.

- **User query-time revision:** Preserved all 12 committed segments through 06:00. Recovered Q09 from the immutable clip-3 graph at 01:30 (requested 01:42; 12 seconds early, no future data). Q01/Q08 use 07:20; Q10 11:45; Q11 21:05; all remaining questions 36:03. Inserted boundaries increase the plan to 76 processing segments. Verified the existing checkpoint exactly matches the new plan prefix, every query cutoff matches a segment boundary, and Q09 contains no later observations. Original end-of-video schedule and interruption history are preserved under remote `provenance/query_schedule_change/`. Resumed the same tmux pipeline and automatic sync; validation now checks each question ID and effective cutoff.


### Qwen full-run continuation — 2026-09-15 UTC

- Observed stop at 2026-09-15T00:03:24Z: MoviePy audio over-read on segment 98, a 30ms query-boundary slice. Checkpoint retained 97 processed segments (94 committed, skipped 23/39/50), four snapshots, zero QA rows.
- Reused the existing project FFmpeg fix only in the isolated Qwen decoder, passing the exact planned audio duration. Real segment 98 test passed (one frame, 0.030s audio); normal segment decoding was byte-identical before/after. Gemini code/prompt and Qwen prompt/model/FPS/decoding unchanged.
- Repair evidence, original exit status, source code and hashes retained under remote `lineage/short_audio_boundary_fix`; policy change recorded in `results/execution_policy_events.jsonl`. Previous Qwen model skips remain explicit.
- Restart requested in the same `egolife_10q_qwen:pipeline` session from checkpoint segment 98; canonical result sync restarted. Final benchmark completion remains pending.

- **M3-Bench parallel evaluation revision:** User requested concurrent A/B/C/D. Preserve completed answers and the active A worker; launch B/C and D adaptation→evaluation as independent workers under the existing `m3bench_bedroom_gemini` tmux session. Per-method locks prevent the original coordinator from duplicating work. Prediction files remain canonical; worker telemetry is private and joined before grading. Snapshot contents and query cutoffs stay unchanged. Parallel timings may include shared GPU/API contention. Entrypoint: `parallel_workers.py`. Verified CUDA tensor operation and both entrypoint imports on Hyperstack 1042997 before launch. At handover A had completed 15/15 and B 2/15; B was preserved, C and D launched under `m3bench_bedroom_gemini:parallel-eval`. Runtime verification is tracked in `parallel_eval/status.json`; no benchmark completion is claimed.

- **Final model-judged scores:** A=10/15, B=3/15, C=3/15, D=1/15. Separate grading is excluded from QA timing.

## Mandol D reruns — 100 candidates / 20 final nodes — 2026-09-14

- **Status:** completed; both tmux runs exited 0 and passed validation (10 EgoLife + 15 bedroom answers). Original A/B/C and two-node D baselines are preserved.
- **Provider / instance:** Hyperstack 1042997, RTX A6000; shared GPU/API contention is possible when the dataset reruns overlap.
- **Requested provider test:** OpenRouter POST embeddings and rerank both returned HTTP 404 for the exact Qwen 0.6B model IDs. Both model endpoint catalogs returned empty endpoint arrays. Retain Qwen3-Embedding-0.6B and Qwen3-Reranker-0.6B on 302.ai; no unrequested model-size substitution.
- **Method:** Original immutable Mandol indexes and timestamp-limited questions; candidate pool up to 100, final 20; unchanged Gemini reasoning model and warm-retrieval stage timers. Offline index-build timings are inherited provenance, not newly incurred QA costs. Separate semantic grading for bedroom; exact-choice grading for EgoLife.
- **Artifacts / entrypoint:** `rerun_mandol_budget.py`; each original remote run contains `reruns/mandol_100_20/{results,config.json,status.json,baseline_method_D_2nodes.jsonl}`. Model/provider smoke tests are in bedroom `provenance/provider_probe/`. Source graph and baseline hashes are checked before/after evaluation.
- **Results:** EgoLife 4/10 (baseline 3/10); bedroom model-judged 4/15 (baseline 1/15). Every answer received 20 distinct evidence nodes. Candidate count was 100 except bedroom Q09, whose snapshot contained 26 eligible memories. Mean/median retrieval ms: EgoLife 2399.98/2375.08; bedroom 2416.64/2387.26. Source graph and baseline hashes verified unchanged. Reports are under each experiment’s `results/gemini/mandol_100_20/`.

### Qwen full-run Mandol retrieval configuration — 2026-09-15 UTC

- User requested Method D candidate pool 100 and final return count 20. Applied before any Method D predictions existed; effective CLI defaults verified as `--candidate-k 100 --top-k 20`. Both the unrelated warmup probe and actual questions use these settings.
- Patched only the isolated Qwen Mandol entrypoint; A/B/C and Gemini unchanged. Each Method D row now includes candidate_k as well as top_k. Original file/hash and new configuration/hash recorded under remote `lineage/mandol_pool_100_final_20`, with canonical provenance `results/mandol_retrieval_config.json`. Running construction was not restarted.

### Qwen interim result fetch and analysis — 2026-09-15 03:51 UTC

- Fetched into the canonical result contract: 134/144 processed, 131 committed, skips 23/39/50, 9 query snapshots, 0 QA rows. No final accuracy/retrieval result exists yet. Nine snapshot source-cutoff checks passed.
- Median committed VLM wall time 183.75 s (mean 184.56 s; P95 254.50 s). Same-segment saved Gemini median 44.39 s across 131 paired segments; descriptive only because prompt/thinking/backend/contention differ. Recent 20-segment interval rate 211.37 s/segment.
- Direct speaker coverage: 88/124 voiced clips include all supplied IDs in episodic memory, 114/124 in either memory class; 438/585 supplied ID occurrences in episodic text, 545/585 in either class. Zero qualified-face clips. Partial ASR on 98/122 retained Deepgram.
- Human-readable analysis: `egolife_m3_jake_day1/results/qwen_thinking/analysis.md`; exact metrics in `provenance/raw/qwen_thinking/construction_analysis.json`. Findings are interim and do not imply grounded semantic accuracy.

### Automatic stop after validated QA — 2026-09-15 UTC

- Superseded by user-requested Hyperstack hibernation; guest poweroff removed. Hibernation API authentication remains unavailable.

- User authorized stopping Hyperstack instance 1042997 once QA is done. Installed enabled systemd timer `qwen-auto-stop.timer` checking every minute. Gate: Qwen and Gemini successful exit, 40 validated unique Qwen predictions, required results/snapshots, and matching Mac checksum-copy receipt. Timer disables itself before guest poweroff; it does not delete or hibernate the VM.
- Mac copy verifier runs independently, refreshes canonical results, verifies SHA-256 for the ready manifest and uploads only the matching receipt. Local record: `provenance/auto_stop_configuration.json`; remote state: `auto_stop_status.json`. Guard negative tests passed for running/failed/duplicate-result cases. User informed that Hyperstack SHUTOFF continues GPU billing; hibernation is needed to release compute billing.

### Qwen QA resume after thinking loop - 2026-09-15

- Status: running. Hyperstack instance 1042997, RTX A6000; same Qwen3.5-4B checkpoint and environment. GPU tensor operation passed and resume verification found all 144 segments processed.
- First controller call failed after 16384 tokens with no completed thinking boundary; 1379 lines contained only 251 unique lines. QA now uses repetition penalty 1.08 and a concise action/answer system instruction. Thinking remains enabled, token cap unchanged. Memory decoding and existing snapshots preserved; Gemini unchanged.
- Prior source, statuses, server log and manifest archived remotely under `lineage/qa_thinking_loop_fix`. Exact policy recorded in `results/qa_generation_repair.json`.
- Resumed through `launch_full.sh` in tmux `egolife_10q_qwen:qa_resume`; durable logs `pipeline.log`, `launcher.log`, `server.log` in the existing full Qwen run. QA results pending verification.
- User subsequently requested non-thinking QA. Stopped the thinking QA restart and launched `egolife_10q_qwen:qa_no_thinking`. Server now sets `enable_thinking=False` for QA and correctly accepts direct final output without a thinking terminator. Memory construction retains thinking=True. Per-call flags and model manifest distinguish the two modes; any partial method rows archived under `lineage/qa_no_thinking` before restarting QA. Repetition penalty 1.08 and concise QA instruction retained.
- Final execution: all 40 trials finished at 13:34 UTC. Reporting initially failed on a duplicate `round` keyword; repaired reporting without rerunning inference. Validation now checks memory and QA thinking modes separately and reports two invalid Method A predictions (Q1/Q2 abstentions). Status: failed strict validation, inference finished. Scores A 0/10, B 5/10, C 3/10, D 1/10. Outputs retained unchanged. Hibernation remains blocked by missing Hyperstack credentials.

## Offline MOSS + GPT-6 Astra entity consolidation — 2026-09-17

- **Status:** 20-minute baseline and two recall rounds completed and verified; 40-minute work stopped at user request.
- **Provider / instance:** Hyperstack `1042997` (`streammeco-a6000-20260914`), RTX A6000 48 GB. Reattached public IP for SSH; original saved run data remains intact.
- **Purpose:** Real audio-backed consolidation of the EgoLife Gemini 20/40-minute committed graphs, followed by official GPT-6 Astra reconciliation and versioned retrieval rebuild.
- **Method:** Full audio prefixes through 1187.92 s and 2387.92 s; MOSS-Transcribe-Diarize 0.9B revision `704aa4a9c304e8520be88901e0d1960158ef5b15`. Upstream helper revision `61bc29cd4120be7b5d3b761b64cd5dff57263642`. No assumption of matching speaker labels across MOSS runs. GPT-6 Astra uses configured official credentials and high reasoning effort; it receives derived transcripts/diarization because raw audio is not supported by Astra.
- **Environment / preflight:** `/opt/streammeco/.venv/bin/python`, torch `2.6.0+cu124`, transformers `5.17.0`; isolated extra audio dependencies under the new run's `deps/`. GPU tensor test, MOSS imports, checkpoint config, and all referenced source clips passed. 16 GB free disk before download. GPU initially idle.
- **Entrypoint / tmux:** `consolidation/scripts/run_moss_hyperstack.sh`; session `consolidation-moss-20260917`; cwd `/opt/streammeco/run/consolidation_live`; durable `moss.log` and `exit_status.txt` there.
- **Artifacts:** Remote checkpoint `/opt/streammeco/models/MOSS-Transcribe-Diarize`; remote prefix audio and raw/normalized outputs under `results/prefix_20` and `results/prefix_40`. Local canonical result root `consolidation/runs/live/`.
- **Results:** pending; model download and official Astra access verified. No success or accuracy claim until output verification.

- **Attempt 1 failure / repair:** MOSS generated the 20-minute transcript, but JSON persistence raised `UnicodeEncodeError` under the remote ASCII locale. Exit status 1 verified; no normalized output or graph published. Preserved `metadata/moss_attempt1.log` and status. Added explicit UTF-8 file writing plus UTF-8 runtime locale; rerun uses tmux `consolidation-moss-20260917-retry1`.
- **40-minute transcript repair:** The initial helper returned success after 16,385 output tokens, but its raw text ended inside a timestamp at ~2372 s. Detected by raw-output inspection; cancelled the pending 40-minute Astra response before publication. Preserving that initial MOSS result and cancelled Astra request. Continuing MOSS from its exact transcript prefix with the same entire 2387.92-second audio input, explicit generation kwargs, and strict full-text parsing; no separately diarized windows are combined. Repair tmux: `consolidation-moss40-continuation-20260917`, log `continuation.log`, exit file `continuation_exit_status.txt` under the same remote run directory.
- **Continuation check:** Exact-prefix continuation emitted only 11 tokens and again ended with an incomplete bracket; strict parsing rejected it and no updated MOSS evidence was published. A targeted full-audio follow-up now requests only the missing tail with explicit prior speaker anchors (no independent speaker-label equality assumption), capped at 1024 output tokens. Tmux `consolidation-moss40-tail-20260917`; `tail.log` / `tail_exit_status.txt`. Raw initial and continuation responses remain retained.

- **User stopped 40-minute work:** targeted tail follow-up also failed strict parsing (exit 1); no active consolidation tmux remains and no 40-minute graph was published. All failed artifacts retained. User redirected work to recall-oriented 20-minute consolidation.
- **Recall iteration:** reuses the verified 275-segment 20-minute MOSS result without new GPU inference; two sequential official GPT-6 Astra calls use cluster defaults with exceptions and versioned confidence/provenance. Results root `consolidation/runs/recall_20/`, durable log `controller.log`.

- **Recall results verified:** baseline 24/224 assigned (10.7%); round 1 and round 2 each 216/224 (96.4%), including 152 named observations (Jake 94, Xiu Shuo 58) and 64 assigned to two unnamed people. Round 1 accepted 71/75 decisions; round 2 accepted 18/18. Official embeddings rebuilt for each version. 29 tests passed and `verify_recall` validated both exact artifact bundles, source preservation, cutoff, registry lineage and retrieval version integrity. Results: `consolidation/runs/recall_20/README.md`. No independent identity accuracy measurement.
- **Native M3 character write-back integration (2026-09-17):** Reused the saved 20-minute
  recall round-1 accepted decisions and original Hyperstack native checkpoint. No new
  Astra or GPU inference run. Local native publication used M3's configured OpenRouter
  `openai/text-embedding-3-large` backend with the existing runtime environment credential.
  Four supported native characters, 216 scoped observations, 87 globally safe features;
  105 text nodes re-embedded, 278 text and all 106 voice embedding collections unchanged.
  Raw contents and edges verified unchanged. 55 tests passed. Results and hashes:
  `consolidation/runs/native_character/`; report: `consolidation/NATIVE_CHARACTER_INTEGRATION.md`.
## Automatic consolidation retrieval cycle - 2026-09-17

- **Status:** completed.
- **Provider / instance:** Hyperstack 1042997, RTX A6000 48 GB; GPU idle before launch.
- **Purpose:** Validate that accepted saved Astra decisions automatically produce a complete native M3 and Mandol retrieval publication, without a separate indexing interval.
- **Method:** Saved 20-minute recall round-1 conclusions; native configured text reindex, full Mandol Qwen3-Embedding-0.6B/302.AI dense rebuild, BM25 and SPLADE rebuild, reload and hybrid search probe. No new Astra call or relation LLM calls.
- **Environment:** isolated `/opt/streammeco/run/consolidation_deployment`; native `/opt/streammeco/.venv/bin/python`; Mandol `/opt/streammeco/mandol-venv/bin/python`. Native import (489 nodes), Mandol import, CUDA arithmetic (4.0), disk and tmux preflight passed.
- **Execution:** tmux `consolidation-auto-reindex-20260917`; results `results/auto_cycle`, durable `validation.log`, `exit_status.txt`, and version-local `mandol_build.log`.
- **Results:** exit 0 on retry; 105 native text nodes re-embedded, 384 native embedding collections unchanged, raw contents/edges unchanged. All 383 Mandol memories verified with dense/BM25/SPLADE indexes; hybrid probe and published-reader query each returned 3 results. Published artifact hashes remained unchanged after querying. Version `v_66eb04de45183ff45dd782fdfb306defbbc592fc4b50113983c2c626420e53d7`; local artifacts `consolidation/runs/deployment_cycle/`.
- **Retry:** first attempt failed to resolve the existing relative SPLADE checkpoint and published nothing. Worker working directory corrected; isolated deployment symlink reuses installed `naver/splade-cocondenser-ensembledistil` weights under the existing `naver/splade-v3` alias. Preflight loaded the model. Successful tmux `consolidation-auto-reindex-20260917-retry1`; failed logs retained under `metadata/attempt1`, model provenance under `metadata/splade_checkpoint_source.json`. Actual remote completion timestamp 2026-09-18 03:16 UTC.

## Online long-horizon Sol / Astra preparation — 2026-09-18

- **Status:** blocked before benchmark launch; diagnostic preflight exited 2 as designed. No substantive benchmark inference started.
- **Provider / instance:** Hyperstack `1042997`, RTX A6000; current SSH endpoint `38.80.122.150`.
- **Requested configuration:** Jake and AEA, C1–C4, paired R1/R2; GPT-5.6 Sol primary (exact model ID unverified, “median” provisionally interpreted as medium); `gpt-6-astra` consolidation with existing high-effort default.
- **Verified:** CUDA tensor operation passed, torch `2.6.0+cu124`, all 109 AEA recording paths present, tmux installed. GPU idle at inspection. Free disk approximately 2.8 GiB.
- **Blockers:** No integrated C1–C4 online entrypoint; TST is offline only, with no verified enrollment/calibrated threshold configuration found; no configured Sol backend. Disk capacity also requires resolution before the full run.
- **Artifacts:** local `online_memory_benchmark/20260918_sol_astra/`; remote `/opt/streammeco/run/online_memory_benchmark/20260918_sol_astra/`. Reused code snapshot, shell references, specification, requested configuration, and source hashes retained separately from results. API credential configuration excluded.
- **Tmux / logs:** `online-memory-sol-astra-20260918-preflight`, retained exited pane; `logs/preflight.log`, `metadata/preflight.json`, `metadata/preflight_exit_status.txt`. Diagnostic results synced locally. No benchmark accuracy or latency results exist.
- **September 18 readiness update:** Official `gpt-5.6-sol` with medium reasoning confirmed by the model endpoint (HTTP 200 locally and on VM); private official credential staged outside run artifacts. Isolated normalized question manifests contain 10 Jake first-ten and 1,994 AEA scheduled questions. New tmux `online-memory-sol-astra-20260918-readiness` exited 2 as designed; GPU arithmetic, media, question manifests and model access passed. Remaining blockers: no integrated online C1–C4 runner, no independently calibrated TST enrollment/threshold for either dataset, with 2.75 GiB free recorded as a capacity risk (the provisional 20 GiB gate was removed after review). Local/remote readiness report and log under `online_memory_benchmark/20260918_sol_astra`. No benchmark inference ran.
- **VM storage inventory:** pip cache 2.2 GiB (~2.13 GiB unique-link) is low-risk to purge. uv cache 8.1 GiB has only ~0.14 GiB unique-link because installed environments share hard links. Five old generated segment directories total ~13.5 GiB unique-link, but are preserved for earlier run provenance/resumption. No deletion performed; actual peak-space need is pending a measured short-prefix run with bounded temp files.
