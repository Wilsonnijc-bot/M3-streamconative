# M3-Agent + StreamMeCo GPU Pipeline Requirements

Last updated: September 17, 2026

## Purpose

This document defines the intended production dependency stack for the original
M3-Agent + StreamMeCo pipeline. A machine is **ready to run** only when every
required component below is installed, configured, and passes its smoke test.

The target pipeline is:

1. Decode video and audio with FFmpeg.
2. Produce speech transcripts and speaker turns using one selected ASR service.
3. compute speaker embeddings locally with SpeakerLab CAM++ on the GPU.
4. Detect faces and compute face embeddings locally with InsightFace Buffalo-L
   on the GPU.
5. Generate multimodal memories with Qwen 3.5 on the GPU.
6. Build and compress StreamMeCo memory graphs.
7. Run M3-Agent control and retrieval over the resulting memory graphs.

## Required Components

| Capability | Required implementation | Execution location | Requirement |
| --- | --- | --- | --- |
| ASR and utterance timing | Deepgram API, Nova-3 | Remote API | Selectable alternative |
| ASR and speaker diarization | OpenRouter `microsoft/mai-transcribe-2`, Azure provider with diarization enabled | Remote API | Selectable alternative |
| Speaker embedding | SpeakerLab CAM++ | GPU | Local model, mandatory |
| Face detection | InsightFace Buffalo-L detector | GPU | Local model, mandatory |
| Face recognition and embedding | InsightFace Buffalo-L recognizer | GPU | Local model, mandatory |
| VLM and memory generation | Qwen 3.5, currently targeted as `Qwen/Qwen3.5-4B` | GPU | Local model, mandatory |
| Agent reasoning | M3-Agent-Control | GPU | Local checkpoint, mandatory |
| Memory generation compatibility | M3-Agent-Memorization assets and StreamMeCo memory code | GPU | Local checkpoint/code, mandatory |
| Text retrieval embeddings | Configured OpenAI-compatible embedding endpoint | Remote API unless replaced locally | Mandatory for retrieval |
| Media processing | FFmpeg, MoviePy, PyDub, OpenCV | CPU/GPU host | Mandatory |

## Selected-ASR Contract

Set `asr_provider` in `StreamMeCo/configs/processing_config.json` to exactly
one alias from `configs/api_config.json`, such as `deepgram-asr` (the default)
or `openrouter-mai-transcribe-2`. Other configured aliases require a supported
transcription adapter. Pipeline readiness requires only the selected service's
credential and a successful transcription request to that service. No fallback
or cross-provider fusion occurs within a construction run.

### Deepgram

- Model: `nova-3`.
- Required output: transcript text, utterance timestamps, and word timing when
  available.
- Required request features: smart formatting, utterance segmentation, and
  diarization metadata.
- Credential: `DEEPGRAM_API_KEY`.

### OpenRouter MAI-Transcribe-2

- Model: `microsoft/mai-transcribe-2`.
- Required upstream provider: Azure.
- Required output format: `verbose_json` with timestamped segments.
- Required provider option: Azure diarization enabled.
- Credential: `OPENROUTER_API_KEY`.

### Selected output

For each audio clip, the selected provider's output is normalized to the
StreamMeCo speech-segment schema:

```json
{
  "start_time": "MM:SS",
  "end_time": "MM:SS",
  "asr": "transcribed speech",
  "speaker": "provider speaker label when available",
  "asr_provider": "selected alias",
  "asr_sources": ["selected alias"]
}
```

The selected provider supplies transcript, timing, and speaker labels when
available. The normalized `MM:SS` intervals have whole-second precision.
Provider failure stops voice construction except in the explicitly logged
EgoLife video-only continuation mode. Per-clip cache sidecars bind the audio
SHA-256 and selected alias; changing providers requires fresh voice graph state.
The standalone TST mapper consumes prepared segments from one declared provider
per run and does not call ASR services.

## GPU Models

### SpeakerLab CAM++

- Framework: SpeakerLab / 3D-Speaker.
- Architecture: CAM++.
- Expected embedding dimension: 192.
- Expected audio input: mono 16 kHz waveform.
- The checkpoint must load without missing or unexpected state-dict keys.
- A smoke test must produce a finite, nonzero 192-dimensional embedding on the
  GPU from a known WAV fixture.

### InsightFace Buffalo-L

- Model pack: `buffalo_l`.
- Required modules: face detection and face recognition.
- CUDA execution must be available through ONNX Runtime GPU.
- A smoke test must detect at least one face in a known image and return a
  finite face embedding.
- The complete Buffalo-L model pack must be present in the InsightFace model
  root. Buffalo-M is not an accepted substitute for this pipeline.

### Qwen 3.5 VLM

- Model family: Qwen 3.5 with visual input support.
- Current target checkpoint: `Qwen/Qwen3.5-4B`, or an explicitly configured
  equivalent Qwen 3.5 checkpoint.
- The model and processor must load entirely from the intended local checkpoint
  or model cache.
- A smoke test must process at least one extracted video frame and return a
  nonempty description while CUDA utilization and GPU memory allocation are
  observed.
- The StreamMeCo memory-generation path must call Qwen 3.5. It must not call
  Gemini.
- Native Qwen thinking is enabled for memory extraction, retrieval-controller
  decisions, and final question answering.
- The completed `<think>...</think>` block is removed before JSON, action-tag,
  or answer parsing. Only the post-thinking response enters StreamMeCo memory or
  benchmark artifacts.
- Thinking-mode generation uses a separate token budget so reasoning cannot
  silently consume the smaller non-thinking response budget.

### Experimental Gemini 3.8 comparison via 302.ai

Gemini is an isolated comparison backend and does not replace the required local
Qwen 3.5 production path. The configured comparison model is
`gemini-3.8-flash` through the OpenAI-compatible 302.ai endpoint. Its credential
must be supplied as `API_302_KEY`; the key must not be written to logs or
committed configuration.

On September 14, 2026, direct connectivity was tested from AutoDL container
`autodl-container-ae124db9f3-5c709e43`:

- Normal access to `https://api.302.ai` timed out from the GPU host.
- AutoDL `/etc/network_turbo` proxy access also failed during TLS negotiation
  and returned no usable 302.ai response.
- Forcing the public address `20.255.184.187` while retaining
  `api.302.ai` as TLS SNI caused the connection to be reset.
- Connecting to `https://20.255.184.187` with HTTP header
  `Host: api.302.ai`, HTTP/1.1, and certificate verification disabled succeeded
  directly from the GPU host. The authenticated `/v1/models` request returned
  HTTP 200 in 2.493 seconds, listed 982 models, and included
  `gemini-3.8-flash`.
- The full 36-frame chat-completion request had not yet been run through this
  direct route when this requirement was recorded. The earlier successful Gemini
  memory test used a local-machine API relay and must not be reported as a
  direct-GPU API call.

Diagnostic command shape, with the key supplied only through the environment:

```bash
curl --noproxy '*' -k --http1.1 \
  -H 'Host: api.302.ai' \
  -H "Authorization: Bearer $API_302_KEY" \
  https://20.255.184.187/v1/models
```

This is a diagnostic workaround, not a production-ready transport. Because the
URL uses an IP address and `-k` disables certificate verification, the client
does not authenticate that it reached the legitimate 302.ai service. Production
readiness requires one of the following:

1. Restore normal DNS/TLS egress from the GPU host so
   `https://api.302.ai/v1` validates normally.
2. Use an authenticated, TLS-verified relay whose identity and access controls
   are explicitly configured.
3. Implement certificate or public-key pinning for the direct-IP route and
   verify that 302.ai supports that transport contract.

The insecure direct-IP workaround must never be treated as satisfying the
production readiness gate by itself.

### M3-Agent checkpoints

The original pipeline expects these local assets:

```text
StreamMeCo/models/M3-Agent-Control/
StreamMeCo/models/M3-Agent-Memorization/
```

Both directories must contain complete model configuration, tokenizer or
processor files, and weight shards. Loading must succeed without downloading
missing files during the readiness test.

## Python and System Dependencies

The intended runtime is Python 3.11 with a CUDA-compatible PyTorch environment.
The original project was built around PyTorch 2.6 and CUDA 12.4. The installed
versions must be mutually compatible with the GPU driver.

Required Python package groups include:

- Core GPU: `torch`, `torchvision`, `torchaudio`, `accelerate`.
- Agent inference: `transformers`, `vllm`, `peft`, `trl` where required by the
  original M3-Agent code.
- Audio and speaker embedding: SpeakerLab source, `soundfile`, `resampy`,
  `pydub`, `torchaudio`.
- Face processing: `insightface`, `onnxruntime-gpu`, `opencv-python-headless`,
  `hdbscan`, `scikit-learn`.
- Video processing: `ffmpeg`, `moviepy`, `pillow`.
- API clients: `httpx`, `openai` for OpenAI-compatible endpoints.
- StreamMeCo utilities: `numpy`, `scipy`, `matplotlib`, `tqdm`.

`nvidia-smi`, `ffmpeg`, and `ffprobe` must be available on `PATH`.

## Configuration and Secrets

Secrets must be supplied through environment variables on the GPU host:

```bash
export DEEPGRAM_API_KEY="..."    # only when deepgram-asr is selected
export OPENROUTER_API_KEY="..."  # only when openrouter-mai-transcribe-2 is selected
```

The text-embedding endpoint and any remaining API-backed reasoning endpoint must
also have valid credentials. API keys must not be committed to Git or copied
into diagnostic reports.

The processing configuration must identify exactly one ASR provider. It must
also point the VLM path to Qwen 3.5 and the agent
paths to the local M3 checkpoints.

## Readiness Gate

The pipeline is ready only when all checks below pass in the same environment:

- [ ] Repository checkout matches the intended StreamMeCo commit.
- [ ] Original `m3_agent` and `mmagent` modules import successfully.
- [ ] CUDA is available to PyTorch.
- [ ] Required GPU memory is available for Qwen 3.5 and M3-Agent execution.
- [ ] FFmpeg can decode a representative MP4 and extract a 16 kHz WAV stream.
- [ ] The selected ASR alias returns nonempty timestamped speech for the WAV fixture.
- [ ] Its normalized segments retain only that provider's provenance and speaker labels.
- [ ] Reusing a cache or graph from another provider is rejected or recomputed as appropriate.
- [ ] CAM++ produces a finite 192-dimensional GPU speaker embedding.
- [ ] Buffalo-L detects a face and produces a finite GPU face embedding.
- [ ] Qwen 3.5 processes an extracted frame and returns nonempty VLM output.
- [ ] M3-Agent-Memorization loads and generates a memory result for one clip.
- [ ] StreamMeCo builds and serializes one memory graph.
- [ ] StreamMeCo compression reads and writes one memory graph.
- [ ] M3-Agent-Control loads and answers one smoke-test question.
- [ ] Text embedding retrieval returns a vector with the expected dimension.
- [ ] Production configuration selects local Qwen 3.5; any Gemini caller remains isolated to explicitly labeled comparison runs.

## Current Repository Gaps

At the time of this document:

1. New construction uses a single selected ASR provider. Historical fused voice
   caches and graphs cannot be resumed without reconstructing voice evidence.
2. `gpu_setup/download_models.py` and `gpu_setup/verify_insightface.py` currently
   target Buffalo-M. They must be changed to download and verify Buffalo-L.
3. The original StreamMeCo Qwen integration targets Qwen 2.5 Omni. The production
   VLM path must be connected explicitly to Qwen 3.5.
4. A full GPU-host readiness run is still required before the pipeline can be
   declared ready.

These gaps are readiness failures, not optional enhancements.


## First-Clip Memory Construction Measurement - 2026-09-14 CST

A fresh 17.63-second Jake Day 1 clip was processed on AutoDL container
`autodl-container-ae124db9f3-5c709e43`. Text memories were embedded through
OpenRouter at `POST /api/v1/embeddings` with model
`openai/text-embedding-3-large`. The verified output dimension was 3,072.

### Shared preprocessing

| Stage | Latency ms |
| --- | ---: |
| Clip decode (89 frames at pipeline FPS) | 2,268.80 |
| Deepgram Nova-3 ASR | 2,658.19 |
| OpenRouter MAI-Transcribe-2 ASR | 8,177.42 |
| Historical two-ASR total | 10,835.62 |
| Audio segmentation | 5.06 |
| CAM++ speaker embeddings (3 x 192 dimensions) | 977.72 |
| Voice graph update | 2.07 |
| Buffalo-L detection and recognition | 3,568.84 |
| Face clustering | 9.39 |
| VLM context construction | 3,920.29 |
| Shared preprocessing wall time | 21,720.25 |

Buffalo-L processed all 89 frames and returned 152 raw face candidates, but none
passed the configured quality and clustering thresholds. The resulting shared
graph therefore contained two voice identities and no face identities.

### Memory branches

| Model | VLM ms | OpenRouter text embedding ms | Graph insertion ms | Equivalence refresh ms | Branch ms | Clip-to-graph ms | Final nodes | Final edges |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Qwen 3.5 4B, local RTX 4090, thinking enabled | 107,613.76 | 3,834.57 | 0.14 | 0.04 | 111,448.75 | 133,169.57 | 11 | 0 |
| Gemini 3.8 Flash, GPU-originated 302.ai request | 25,485.34 | 4,799.15 | 0.41 | 0.05 | 30,285.46 | 52,006.62 | 10 | 1 |

Qwen produced six episodic and three semantic memories. Gemini produced five
episodic and three semantic memories. The Gemini semantic memory referencing
`<voice_0>` created one voice-to-semantic edge; Qwen generated no explicit
identity references, so its graph contained no edges.

The run used FLA successfully, but `causal_conv1d` remained ABI-incompatible
with PyTorch 2.6.0+cu124. Transformers used its correct but slower reference
PyTorch causal-convolution implementation. Qwen timing therefore includes that
fallback and is not an optimized-kernel latency measurement.

Full raw VLM responses, parsed memories, detailed embedding timings, nodes,
edges, and graph deltas are stored in
`egolife_m3_jake_day1/first_clip_vlm_compare_openrouter_20260914/comparison.md`.
