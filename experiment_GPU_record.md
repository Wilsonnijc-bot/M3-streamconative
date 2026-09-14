# GPU Experiment Record

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
