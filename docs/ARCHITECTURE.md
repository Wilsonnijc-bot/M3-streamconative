# M3-StreamConative Architecture

This document describes the **current repository architecture and its runtime/model dependencies** for M3-StreamConative. It covers the construction path, alternative Mandol retrieval path, online TST condition, implemented native character consolidation, and opt-in asynchronous streaming runtime. Recorded deployment results are distinguished from current configuration and deterministic runtime tests.

**Current online benchmark backend roles:** Terra (`gpt-5.6-terra`, medium reasoning)
constructs video memories and generates the final answer after either R1 or R2 retrieval. Sol (`gpt-5.6-sol`, high
reasoning) performs memory consolidation for C3/C4. Both use the official OpenAI
Responses API. Terra replaces Qwen 3.5 4B for this benchmark's memory construction.
Qwen remains a retained legacy backend implementation.
Historical Astra results below describe earlier experiments, not the selected
benchmark backend. The existing directory name `20260918_sol_astra` is retained
for artifact continuity; model selection comes from its `configs/run_request.json`.

> **Source boundary.** This document is based on files in this repository plus the maintainer-specified integration contract for the current branch (for example, the Mandol 1024-D dense path). No external model documentation is used to fill gaps. When the repository does not pin an exact checkpoint or implementation, that dependency is explicitly marked **un-pinned** rather than guessed.

[Earlier architecture illustration](architecture.png). The diagrams below and section 11 describe the current consolidation/runtime additions.

---

## 1. System at a glance

The project has three major phases:

```text
                               MEMORY CONSTRUCTION

Video clip + audio
      │
      ├───────────────┐
      │               │
      ▼               ▼
Selected ASR      Face pipeline
Deepgram OR MAI   InsightFace Buffalo-L
or adapter        + HDBSCAN clustering
      │               │
      ├───────────────┐
      │               │
      ▼               ▼
CAM++ speaker    ECAPA/TST speaker
embeddings      192-D per utterance
(C1)            (C2/C3/C4)
      │               │
      └───────┬───────┘
              ▼
      native M3 voice policy
      search → match/update
      or create voice node
              │
              ├───────────────┐
              │               │
              ▼               ▼
       face embeddings        │
              │               │
              └───────┬───────┘
                      ▼
              multimodal VLM backend
              memory generation
              ├─ episodic memories
              ├─ semantic memories
              └─ face/voice equivalence statements
              │
              ▼
 native canonical retrieval text
              │
              ▼
 text-embedding-3-large
 3072-D text vectors
              │
              ▼
          M3 VideoGraph
  ┌─────────────────────────────────────┐
  │ episodic / semantic / voice / img   │
  │ character mappings                  │
  │ text_nodes_by_clip                  │
  │ event_sequence_by_clip              │
  └─────────────────────────────────────┘
              │
              ├──────── raw graph ───────────────────────────────┐
              │                                                 │
              └─ optional StreamMeCo compression ── compressed ──┤
                                                                │
                         QUERY TIME                             ▼

               ┌─────────────────────────────┬─────────────────────────────┐
               │ Path A: native retrieval    │ Path B: Mandol integration  │
               │                             │                             │
query ─────────► text-embedding-3-large      │ query                       │
               │ 3072-D                     │   │                         │
               │   │                        │   ▼                         │
               │ cosine search over         │ BM25 + 1024-D dense +      │
               │ episodic/semantic nodes    │ SPLADE sparse               │
               │   │                        │   │                         │
               │ clip aggregation           │ fusion / graph expansion    │
               │   │                        │   │                         │
               │ top-k evidence             │ optional reranker           │
               │                             │   │                         │
               │                             │ top-k evidence              │
               └─────────────────────────────┴─────────────────────────────┘

                 evidence from the selected retrieval path
                                  ↓
                  Terra → streamed final answer (medium)

                  ASYNCHRONOUS CONSOLIDATION (OPT-IN)
              frozen prefix → Sol → native character patch
              → commit between clip writes → background reindex
              → verified native/Mandol retrieval publication
```

The two retrieval paths are **alternatives**. The target direct path deliberately removes the original iterative controller loop: one user query produces one retrieval invocation and returns evidence. Mandol is a second retrieval backend, not a second stage after native retrieval. The standalone frozen-enrollment TST utility is omitted from this production construction/retrieval diagram; the online `TSTVoiceMapper` is part of C2/C3/C4 construction and writes native voice nodes.

Native live retrieval includes newly constructed hot memories while consolidation runs. A published Mandol checkpoint includes only its indexed snapshot. Consolidation updates native `character_N` identities; it does not introduce a separate runtime `person_N` layer. Canonical retrieval text is produced before embedding, while original memory text remains evidence.

---

# 2. Dependency inventory

This section is the dependency map to consult first when reproducing or modifying the pipeline.

Dependency status terminology:

- **Pinned** — selected directly by current code/config or explicitly recorded by a repository runbook.
- **Integration contract** — required by the current M3↔Mandol design, but the exact checkpoint is not pinned in the repo yet.
- **Un-pinned** — the component exists in the architecture, but selecting a concrete model remains a configuration/implementation task.
- **WIP** — not yet a completed dependency of the production path.

## 2.1 Model-level dependencies

| Stage | Dependency | Exact repo configuration | Execution | Output used by downstream code | Status |
| --- | --- | --- | --- | --- | --- |
| Speech recognition / utterance timing | **Deepgram Nova-3**, selectable | Provider key `deepgram-asr`; runbook pins `nova-3` | Remote API | Timestamped transcript / utterance evidence | **Pinned alternative** |
| Speech recognition / diarization | **Microsoft MAI-Transcribe-2** through OpenRouter, Azure provider, selectable | Provider key `openrouter-mai-transcribe-2`; runbook pins `microsoft/mai-transcribe-2` | Remote API | Timestamped transcript + speaker-turn evidence | **Pinned alternative** |
| Speaker embedding | **SpeakerLab CAM++ / CAMPPlus** | `speaker_embedding_model: speakerlab-campplus`; checkpoint `models/camplus/campplus_cn_en_common.pt` | Local GPU | **192-D** normalized voice embeddings | **Pinned** |
| Online TST speaker mapping | **SpeechBrain ECAPA-TDNN** | `speechbrain/spkrec-ecapa-voxceleb`; immutable revision pinned by the run config and loaded locally without network access | CUDA | **192-D** embeddings used by native M3 voice-node search, update, and creation; no pre-enrollment | **Selected for C2/C3/C4 in the online benchmark** |
| Face detection | **InsightFace Buffalo-L detector** | `face_model: buffalo_l`; model root `models/insightface` | Local GPU through ONNX Runtime | Face bounding boxes + detection metadata | **Pinned** |
| Face recognition / embedding | **InsightFace Buffalo-L recognizer** | same Buffalo-L pack; `allowed_modules=[detection, recognition]` | Local GPU through ONNX Runtime | Face embeddings stored in `img` nodes | **Pinned; vector dimension is not explicitly asserted by repo code** |
| Multimodal memory generation | **VLM backend** | Native `mmagent.memory_backend` selector; current examples are Terra, Qwen, and the optional Gemini comparison path | Local or remote model, depending on backend, with sampled frames and face/voice evidence | Episodic text and semantic conclusions using native IDs | **Backend role; Terra selected for the online benchmark** |
| Native M3 text embedding | **`text-embedding-3-large`** | hard-coded alias in construction and retrieval; measured run uses OpenRouter `openai/text-embedding-3-large` | Remote OpenAI-compatible endpoint in current deployment | **3072-D** vectors for episodic/semantic nodes and queries | **Pinned** |
| Character mapping | Native deterministic identity logic | legacy union-find construction; consolidation updates native characters and scoped assignments | CPU | Authoritative `character_mappings`, metadata and scoped mappings | **Implemented; section 5.3** |
| Consolidation audio evidence | **MOSS-Transcribe-Diarize** | `OpenMOSS-Team/MOSS-Transcribe-Diarize`; checkpoint revision recorded per run | Consolidation worker calls configured inference server | Same-window transcript, run-local speaker labels and session-time alignments | **Historical 20-minute evidence verified; incremental orchestration tested with mocks** |
| Consolidation reasoning | **GPT-5.6 Sol** | benchmark selects `gpt-5.6-sol`, high reasoning, official Responses API | Remote API, outside live mutation path | Structured decisions projected into native character state | **Selected for C3/C4; earlier integration fixtures used Astra** |
| StreamMeCo compression | **No learned model** | NumPy + scikit-learn KMeans over embeddings already in the graph | CPU | Reduced text-node graph | **Pinned** |
| Native query retrieval | No additional retrieval checkpoint | query uses `text-embedding-3-large`; graph uses cosine similarity | API + CPU | Ranked text nodes / clips | **Pinned** |
| Mandol lexical branch | **BM25** | specified in `mandoladaptor.md` | CPU/index layer | lexical candidates | **Pinned algorithm** |
| Mandol dense branch | **Qwen3-Embedding-0.6B, 1024-D** | current adapter defaults to OpenRouter; verified consolidation cycle used 302.AI | API + FAISS index | dense candidates | **Selected; provider distinction in section 9.3** |
| Mandol sparse branch | **SPLADE sparse retrieval** | verified deployment uses cocondenser weights under local `naver/splade-v3` alias | model/index layer | sparse candidates | **Recorded deployment provenance; section 9.3** |
| Mandol reranking | Reranker | reranker is part of planned/used Mandol hybrid stack | model layer | final candidate ordering | **Exact checkpoint un-pinned** |
| Mandol relation construction | Optional relation-extraction LLM | generic adapter defaults to configured `gemini-3.8-flash-302`; consolidation deployment disables relations | API depending configuration | searchable `entity_relation` MemoryUnits and relations | **Optional; not exercised by verified consolidation cycle** |
| Final answer generation | **GPT-5.6 Terra** | `gpt-5.6-terra`, medium reasoning, official streamed Responses API | Remote API, after R1 or R2 retrieval | Final answer; first content-token latency recorded | **Selected main benchmark backend** |

### The most important embedding distinction

There are **five distinct embedding spaces** across the online M3 conditions and Mandol; equal dimensions do not make them compatible:

```text
Speaker identity space
CAM++
192-D
used only to match / update voice nodes

Online TST speaker identity space
SpeechBrain ECAPA-TDNN
192-D (a different space from CAM++)
used by native M3 voice-node match / update / create
no pre-enrollment; identities emerge incrementally within each graph

Face identity space
InsightFace Buffalo-L
repo does not hard-code the vector dimension
used only to match / update img nodes

Native text retrieval space
text-embedding-3-large
3072-D in the verified repository deployment
used by episodic + semantic memories and direct query retrieval

Mandol dense text space
1024-D
separate Mandol encoder/index
used only by the Mandol retrieval backend
```

Therefore:

- CAM++ and ECAPA vectors cannot be compared or placed in each other's caches, despite both being 192-D. They follow the same native M3 identity policy in separate embedding spaces;
- a speaker vector is **not** a text retrieval vector;
- a Buffalo-L face vector is **not** a text retrieval vector;
- the M3 3072-D `text-embedding-3-large` vector cannot be inserted directly into the Mandol 1024-D dense index;
- the Mandol adapter must hand text to Mandol's encoder/index builder and let Mandol create its own dense/sparse representations.

That separation is a hard dependency boundary, not merely an implementation detail.

---

# 3. Repository source-of-truth hierarchy

The repo contains implementation code, configs, runbooks, and older compatibility paths. For this document, the interpretation order is:

1. **Current executed source code** under `StreamMeCo/mmagent`, `StreamMeCo/m3_agent`, `consolidation`, `Mandol/src/mandol/adapters/m3`, and `StreamMeCo/streammeco.py`.
2. **Current configuration** under `StreamMeCo/configs/` and `consolidation/deployment.json`, checked against the selected runtime adapter.
3. **Deployment/runbook evidence** in `GPU_PIPELINE_REQUIREMENTS.md` and `HYPERSTACK_GPU_RUNBOOK.md`.
4. **Adapter design contract** in `mandoladaptor.md` for the Mandol path.
5. Legacy controller/model assets are described separately and are not treated as required by the new no-controller retrieval path.

This matters because some historical comments/readiness notes describe older behavior that the current source has already changed.

---

# 4. Memory construction pipeline

## 4.1 Clip decoding and preprocessing

Primary orchestration:

```text
StreamMeCo/m3_agent/memorization_memory_graphs.py
    streaming_process_video(...)
        └─ process_video_clip(clip_path)
             ├─ base64_video
             ├─ base64_frames
             └─ base64_audio
```

The pipeline is organized around clip IDs. `processing_config.json` currently specifies:

```text
interval_seconds = 30
fps              = 5
qwen_video_fps   = 2
```

The general host/media dependency group is:

```text
FFmpeg / ffprobe
MoviePy
PyDub
OpenCV
Pillow
PyAV
```

The raw clip is then processed in this order in `process_segment()`:

```text
1. process_voices(...)
2. process_faces(...)
3. generate_memories(...)
4. batch text embedding
5. insert episodic nodes
6. insert semantic nodes
7. after all clips: refresh_equivalences()
```

The voice and face stages therefore run **before** the VLM memory stage because their IDs and evidence are injected into the selected backend context.

---

## 4.2 Audio transcription dependency

### One selected provider per construction run

`processing_config.json` selects one alias, currently:

```json
"asr_provider": "deepgram-asr"
```

Set it to `openrouter-mai-transcribe-2` to run MAI instead. Other aliases can be used when `configs/api_config.json` has a supported transcription adapter. `voice_processing.py`, transcript generation, and first-ten-clip prefetch call **only that alias** for each clip. No second provider is requested, compared, or merged. A failure of the selected service fails the voice stage, except the explicitly logged EgoLife video-only continuation mode. Switching providers for a memory run requires fresh voice state.

The repo runbook resolves the provider aliases to:

| Provider alias | Actual model/service | Important output |
| --- | --- | --- |
| `deepgram-asr` | Deepgram **Nova-3** | transcript text, utterance/timing evidence |
| `openrouter-mai-transcribe-2` | **`microsoft/mai-transcribe-2`**, Azure provider | verbose timestamped segments + diarization evidence |

Only the **selected** API is a dependency of voice construction, not final retrieval. Each normalized segment has `asr_provider` and a one-element `asr_sources` list. The production normalizer rounds `MM:SS` timestamps to whole seconds; this is not raw word-level timing.

### Credentials

The selected ASR provider requires its corresponding credential:

```bash
DEEPGRAM_API_KEY   # deepgram-asr
OPENROUTER_API_KEY # openrouter-mai-transcribe-2
```

`chat_api.py` also loads provider routing from `configs/api_config.json`. That file is a runtime configuration dependency. Exact secrets must remain outside version-controlled documentation.

### Segment filter

For the production CAM++ graph path, only speech segments meeting:

```text
min_duration_for_audio = 2 seconds
```

are passed to the speaker-embedding stage. The separate TST runner does not inherit this 2-second filter.

---

## 4.3 Speaker embedding dependencies: CAM++ and online TST

Implementation:

```text
StreamMeCo/mmagent/voice_processing.py
```

Imports:

```python
from speakerlab.process.processor import FBank
from speakerlab.models.campplus.DTDNN import CAMPPlus
```

Current speaker feature pipeline:

```text
transcribed / diarized speech segment
        │
        ▼
extract waveform for the segment
        │
        ▼
mono 16 kHz
        │
        ▼
FBank(
    feat_dim=80,
    sample_rate=16000,
    mean_nor=True
)
        │
        ▼
CAMPPlus(feat_dim=80, embedding_size=192)
        │
        ▼
192-D speaker embedding
        │
        ▼
normalize_embedding(...)
        │
        ▼
VideoGraph.search_voice_nodes(...)
        │
        ├─ matched → update existing voice node
        └─ unmatched → create new voice node
```

Checkpoint resolution order:

```text
$CAMPLUS_CHECKPOINT
    else
processing_config["speaker_embedding_checkpoint"]
    = models/camplus/campplus_cn_en_common.pt
```

Runtime location:

```python
embedding_model.to(torch.device("cuda"))
```

So CAM++ is the **C1 local GPU speaker frontend** for memory construction, but it is **not called during normal text query retrieval**.

### Voice identity matching

Voice matching occurs inside the `VideoGraph`; it is not an LLM decision.

```text
metric        = cosine similarity
threshold     = audio_matching_threshold = 0.6
stored limit  = max_audio_embeddings = 20 per voice node
```

A new segment is compared to existing `voice` nodes. If the best candidate passes the threshold, the node is updated; otherwise a new voice node is created.

The voice node retains ASR text entries in `metadata["contents"]` and at most 20 embeddings from the selected speaker frontend. Per-clip `clip_<id>_voices.json` caches retain segment audio, rounded timestamps, text, local speaker labels, and embeddings separately. Their `.provider.json` sidecars bind the selected alias and input-audio SHA-256; legacy/fused caches are recomputed. The graph records its `asr_provider` and rejects resuming voice processing under another provider (or resuming an unlabeled legacy voice graph). The graph does not maintain a named person's complete raw-audio collection.

This is an important limitation for persistent identity: an embedding miss can create a new voice node even if the physical speaker is the same person. The implemented consolidation stage addresses supported fragmentation through native character merges and scoped assignments (section 11), without changing the CAM++ matching policy.

### Online TST speaker identity mapping

The original `StreamMeCo/mmagent/tst_mapper.py` is the alternative speaker frontend for C2/C3/C4. The benchmark imports it directly from the production package and attaches one `TSTVoiceMapper` to each independent `VideoGraph`; C1 leaves the mapper unset and uses CAM++. Both frontends call `mmagent.speaker_mapping.assign_voice`, which owns candidate scoring and the native match/update/create decision before returning immutable assignment evidence.

`TSTVoiceMapper` validates `enrollment_policy: online_native_m3` and `pre_enrollment: false`. It loads the pinned SpeechBrain `spkrec-ecapa-voxceleb` snapshot and extracts one or more 192-D ECAPA vectors from each incoming utterance using the configured 16 kHz, 4-second window and 1.5-second shift policy. It then passes those vectors directly to the same native M3 voice-node policy used by CAM++:

```text
incoming utterance
        │
        ▼
SpeechBrain ECAPA, 192-D vector(s)
        │
        ▼
VideoGraph.search_voice_nodes(...)
        │
        ├─ accepted match → VideoGraph.update_node(...)
        └─ no match       → VideoGraph.add_voice_node(...)
```

There is no pre-enrollment, named-identity gallery, or fixed gallery in this online path. Each of C2, C3, and C4 therefore builds voice identities incrementally in its own graph. The graphs retain only their own ECAPA voice-node history; C1's CAM++ vectors and the TST graphs' ECAPA vectors are never mixed. The native threshold and retained-embedding cap remain `audio_matching_threshold = 0.6` and `max_audio_embeddings = 20`.

`offline=True` is passed to the SpeechBrain loader only to require that the pinned model snapshot is already local (`local_files_only=True`). It controls model acquisition, not identity mapping: utterances still arrive online, are embedded, searched against the current graph, and either update an existing voice node or create a new one. The standalone `tst/runner.py` remains a separate frozen-enrollment, score/mapping utility and is not the online benchmark path.

---

## 4.4 Face dependency: InsightFace Buffalo-L

Implementation:

```text
StreamMeCo/mmagent/face_processing.py
```

Model initialization:

```python
FaceAnalysis(
    name="buffalo_l",
    root=<INSIGHTFACE_MODEL_ROOT or models/insightface>,
    allowed_modules=["detection", "recognition"],
    providers=["CUDAExecutionProvider", "CPUExecutionProvider"],
)
```

The current deployment therefore needs both:

1. Buffalo-L **detection** assets.
2. Buffalo-L **recognition/embedding** assets.

The runbook checks, among other files:

```text
models/insightface/models/buffalo_l/det_10g.onnx
models/insightface/models/buffalo_l/w600k_r50.onnx
```

Model-root resolution:

```text
$INSIGHTFACE_MODEL_ROOT
    else
processing_config["face_model_root"]
    = models/insightface
```

### Face processing path

```text
sampled video frames
       │
       ▼
InsightFace Buffalo-L
 detection + recognition
       │
       ▼
face candidates + face_emb
       │
       ▼
HDBSCAN clustering
       │
       ▼
quality filtering
       │
       ▼
representative embeddings
       │
       ▼
VideoGraph.search_img_nodes(...)
       │
       ├─ matched → update img node
       └─ unmatched → create img node
```

There are **two quality/filter stages** in the repository and they should not be conflated:

1. `face_clustering.py` pre-filters candidates at approximately `face_detection_score >= 0.8` and `face_quality_score >= 20` before HDBSCAN.
2. `face_processing.py` then applies the stricter graph-admission thresholds from `processing_config.json`:

```text
face_detection_score_threshold = 0.85
face_quality_score_threshold   = 22
max_faces_per_character        = 3
```

### Face identity matching

The final graph association uses cosine similarity over face embeddings:

```text
threshold = img_matching_threshold = 0.3
max stored image embeddings = 10
```

The repository does not need a separate text model to match face nodes. Face identity is handled entirely in the Buffalo-L embedding space.

> The exact face-embedding dimensionality is intentionally not hard-coded in this document because the current repository code obtains it from the model output rather than declaring a dimension contract.

---

## 4.5 Multimodal Memory Construction

Memory generation is a **multimodal VLM backend role**, selected through the native
`mmagent.memory_backend` interface. The backend receives chronological sampled frames,
qualified face crops with native IDs, timestamped ASR text, and voice IDs. It returns
the existing memory schema:

```text
video_description        → episodic memories
high_level_conclusions   → semantic memories
```

The current repository includes multiple backend implementations. Terra is the
selected online benchmark backend; Qwen is the retained local-model implementation;
the Gemini path is an experimental comparison backend. These are backend examples,
not a constraint on the memory graph contract. The backend may be local or remote,
but it must preserve native IDs and return nonempty string lists for both memory
classes. Request/response provenance and token usage are retained when the backend
provides them.

The shared context is constructed from multiple upstream products:

```text
video clip
+
qualified face examples labeled <face_ID>
+
voice segments labeled <voice_ID>
  including timestamps and selected-provider ASR text
+
structured memory-generation prompt
        │
        ▼
configured multimodal VLM backend
```

The memory is only as identity-aware as the face/voice nodes and ASR labels supplied
to the backend. The backend must not replace native graph identity matching; it can
emit evidence such as:

```text
Equivalence: <face_x>, <voice_y>
```

Those equivalence statements are later consumed by `VideoGraph.refresh_equivalences()` to create character mappings.

---

## 4.6 Text embedding dependency: `text-embedding-3-large`

After memory generation, the current shared construction path canonicalizes and batches the text:

```python
raw_texts = episodic_memories + semantic_memories
retrieval_texts = prepare_texts(video_graph, raw_texts)
get_embeddings_batch("text-embedding-3-large", retrieval_texts)
```

The vectors are split back into episodic and semantic sets and inserted into the graph. Original `metadata['contents']` stays unchanged; `retrieval_contents`, `retrieval_identity_trace` and `embedding_input_fingerprint` separately describe the encoded representation. Precomputed handoffs must match the canonical input. The legacy memory-processing path uses the same preparation helper.

The repository's measured deployment records:

```text
endpoint family : OpenAI-compatible embeddings API
model            : openai/text-embedding-3-large through OpenRouter
vector dimension : 3072
```

Therefore the **native M3 textual memory space is 3072-D in the current deployment**.

### Where this same text model is reused

It is used in both places:

```text
MEMORY SIDE
Qwen text
  → native identity resolution / canonical retrieval text
  → text-embedding-3-large
  → 3072-D embedding stored on episodic/semantic node

QUERY SIDE
user query
  → text-embedding-3-large
  → 3072-D query embedding
  → cosine similarity against node vectors
```

This shared encoder is what makes the direct M3 retrieval path possible without a separate learned retriever.

---

# 5. M3 VideoGraph representation

Implementation:

```text
StreamMeCo/mmagent/videograph.py
```

The graph is the canonical memory representation before Mandol adaptation.

## 5.1 Node types

| Node type in code | Payload / embedding source | Main role |
| --- | --- | --- |
| `episodic` | VLM episodic text + 3072-D `text-embedding-3-large` vector | clip-grounded observations/events |
| `semantic` | VLM semantic text + 3072-D `text-embedding-3-large` vector | higher-level facts/conclusions/equivalence statements |
| `voice` | ASR content + one or more 192-D CAM++ or ECAPA vectors | speaker evidence / speaker identity cluster |
| `img` | face crops + one or more Buffalo-L face vectors | face evidence / visual identity cluster |

The term **face node** in diagrams corresponds to code type `img`.

## 5.2 Edge dependencies

When text memories are inserted, `parse_video_caption(...)` detects explicit entity references in the text and creates graph edges from the text node to corresponding face/voice nodes.

Conceptually:

```text
episodic / semantic text node
        │
        ├── edge → voice_7
        └── edge → img/face_3
```

This is why the VLM prompt's stable `<voice_ID>` / `<face_ID>` tags matter: they connect natural-language memories back to multimodal evidence.

## 5.3 Character mappings

`refresh_equivalences()` scans the graph for face/voice equivalence information and applies a union-find/disjoint-set algorithm.

```text
semantic equivalence evidence
        │
        ▼
union(face_x, voice_y)
        │
        ▼
connected identity component
        │
        ▼
character_0
    ↔ face_x
    ↔ voice_y
```

The output includes:

```text
character_mappings
reverse_character_mappings
```

Important dependency rule:

> Character mapping has **no additional embedding model**. It depends on the upstream face/voice node IDs plus equivalence evidence generated into the graph, then uses deterministic union-find to consolidate those links.

This describes legacy construction. Consolidation now updates the same native characters rather than introducing a second identity namespace. `reverse_character_mappings` remains derived only from current global ownership; there is no pre-consolidation runtime fallback.

The existing character-to-feature-list schema is extended with:

| Native field | Role |
| --- | --- |
| `character_metadata` | Canonical name, aliases, confidence, evidence, merged IDs and provenance |
| `observation_character_mappings` | Observation ID → native character |
| `reference_character_mappings` | Immutable memory node/content index/span → native character |
| `identity_observations`, `reviewed_feature_support` | Reviewed versus provisional support, votes and completeness |
| `identity_revision`, `identity_history`, identity cutoff/session fields | Versioned evidence horizon and audit |
| `retired_character_ids`, `next_character_id` | Retired-ID history and monotonic allocation |

`VideoGraph.resolve_identity` uses exactly this order: observation assignment, reference-occurrence assignment, current global mapping, raw feature ID. Resolved characters display their canonical name or, if unnamed, `character_N`. `person_N` is only a temporary proposal/debug alias. Repeated mentions can resolve separately through `node_id:content_index:start:end` occurrence keys.

Reviewed global feature ownership requires complete coverage and agreement. Mixed/incomplete features retain supported scoped assignments but no unsafe global name. Appends invalidate completeness. A new observation may inherit a provisional scoped assignment only when independent reviewed votes exceed **75% of all known observations**, including unresolved ones; exactly 75% fails and provisional assignments never cast votes. A majority never names an unscoped mixed-feature mention.

Survivors prefer existing bound native characters, otherwise compatible greatest supported-observation overlap with lowest numeric-ID tie breaking. Only exhausted affected characters with one supported survivor are retired; partial moves preserve remaining identity. Refresh/rebuild preserves consolidated metadata, scoped assignments, lineage and removed mixed ownership. Existing equivalence statements remain evidence. Runtime-managed graphs also protect native ID stability while historical work is running.

## 5.4 Temporal indexes

Text nodes carry clip provenance through metadata such as:

```text
metadata["timestamp"] = clip_id
```

The graph also maintains structures including:

```text
text_nodes_by_clip
event_sequence_by_clip
```

These are algorithmic indexes, not model dependencies.

---

# 6. StreamMeCo memory compression

Implementation:

```text
StreamMeCo/streammeco.py
```

The compressor is a callable operation:

```python
compress_graph(graph, alpha=0.1)
    → updated_graph, summary
```

## 6.1 Critical dependency property: no new model

StreamMeCo compression does **not** call:

- Qwen;
- `text-embedding-3-large`;
- CAM++;
- Buffalo-L;
- Mandol encoders;
- a separate compression neural network.

It consumes embeddings that are **already attached to nodes** in the M3 graph.

The helper `_node_embedding(node)` returns one vector per node, averaging the node's existing vectors when necessary.

## 6.2 Algorithm dependencies

```text
NumPy
scikit-learn KMeans
scikit-learn normalize
existing graph edges
existing node embeddings
```

Current constants:

```text
FIRST_CLASS_CLUSTER_RATIO = 0.05
FIRST_CLASS_KEEP_RATIO    = 0.7
SECOND_CLASS_KEEP_RATIO   = 0.7
alpha default             = 0.1
```

The implementation distinguishes text memories with and without media associations, applies KMeans/farthest-selection for one class and graph/embedding importance for another, removes selected text nodes, then refreshes equivalences.

## 6.3 Dependency ordering

The compression boundary is therefore:

```text
all construction models have already run
        │
        ▼
complete M3 VideoGraph
        │
        ▼
optional StreamMeCo compression
        │
        ▼
compressed M3 VideoGraph
```

If Mandol is being built from the compressed graph, the adapter/index build should occur **after compression**, otherwise Mandol can index memories that were subsequently removed.

---

# 7. Retrieval Path A — direct M3 retrieval, no controller

The target native path reuses the retrieval primitive in:

```text
StreamMeCo/mmagent/retrieve.py
```

The core function is:

```text
retrieve_from_videograph(...)
```

## 7.1 Query-time dependencies

```text
user query
   │
   ▼
query preparation (human-name queries unchanged for consolidated graphs)
   │
   ▼
text-embedding-3-large
3072-D query embedding
   │
   ▼
VideoGraph.search_text_nodes(...)
cosine similarity
   │
   ▼
node scores
   │
   ▼
aggregate scores by clip
   │
   ▼
top-k clips / memories
```

There is **no separate native dense retriever checkpoint**. The exact same text embedding family used to encode memory nodes is used to encode queries.

## 7.2 Search metric

`VideoGraph.search_text_nodes` performs cosine similarity over text-node embeddings. `retrieve_from_videograph()` then aggregates node scores into clip scores using a configured mode such as:

```text
max
sum
mean
```

The direct search therefore depends on:

```text
text-embedding-3-large API
NumPy / scikit-learn cosine similarity
VideoGraph's existing text embeddings
character mappings when query expansion/back-translation is used
clip timestamps for clip aggregation
```

It does **not** depend on Mandol.

The existing call path is `retrieve_from_videograph` → configured query embedding → `VideoGraph.search_text_nodes` → clip/node ranking → `search` result assembly → `translate(..., node_id=...)` → native canonicalization/resolution. Consolidated queries are not expanded back into voice IDs, and scoped characters are not excluded by the legacy raw-feature prefilter. Non-consolidated graphs retain legacy behavior.

With an attached runtime, `_resolve_graph` captures a request-local read snapshot including hot memories. A publication-directory argument loads one verified version through `VideoGraph.load_current`. Earlier-cutoff retrieval must choose an appropriate historical version; filtering a later graph cannot undo later identity evidence.

## 7.3 What “no controller call” means

The repository still contains the original M3 controller-oriented code and config fields such as:

```text
max_retrieval_steps
route_switch
planning
api_chat_model
```

Those belong to the legacy/original control path.

For the M3-StreamConative target architecture:

```text
query
  → one deterministic/native retrieval invocation
  → returned evidence
```

No LLM should iteratively decide to search again. The existence of old controller code does not make M3-Agent-Control a dependency of the new direct retrieval path.

### Native direct path dependency summary

| Dependency | Construction time | Query time |
| --- | :---: | :---: |
| Qwen 3.5 4B | Yes | No |
| Selected Deepgram or MAI ASR | Yes | No |
| CAM++ | Yes | No |
| Buffalo-L | Yes | No |
| `text-embedding-3-large` | Yes | **Yes** |
| StreamMeCo | Optional | No; operates before retrieval |
| M3-Agent-Control | No for target path | **No** |
| Mandol | No | **No** |

---

# 8. Retrieval Path B — Mandol integration

Design source:

```text
mandoladaptor.md
```

Mandol does not replace M3 memory construction. It consumes the selected M3 graph through an adapter and builds a separate retrieval representation.

## 8.1 Adapter input boundary

Preferred flow:

```text
M3 VideoGraph
   │
   ├─ raw graph, if compression disabled
   │
   └─ compressed graph, if compression enabled
            │
            ▼
      M3 → Mandol adapter
```

If compression is enabled, `mandoladaptor.md` places adaptation after compression so Mandol only receives memories that survive compression.

## 8.2 Exact representation mapping

### Episodic memory

```text
M3 episodic node
      ↓
Mandol MemoryUnit(type=episodic)
```

### Semantic memory

```text
M3 semantic node
      ↓
Mandol MemoryUnit(type=semantic)
      +
semantic/hierarchical organization in Mandol
```

### Voice and face nodes

They are **not directly indexed as standalone Mandol text MemoryUnits**.

Instead:

```text
M3 face nodes ───┐
                 ├─→ EntityRegistry / entity evidence
M3 voice nodes ──┘
```

### Character mappings

M3's `character_N` identifiers are carried into Mandol as entity identity anchors rather than asking the Mandol relation builder to rediscover whether a face and voice belong to the same existing character.

```text
M3 character_0
      ↓
Mandol entity: character_0
```

This keeps identity ownership upstream in M3.

The implemented exporter uses canonical retrieval text and native scoped assignments, rejects identity-dirty graphs, and does not infer a mixed feature's name from adjacency. Raw contents remain evidence. Canonicalization therefore precedes Mandol's own dense/sparse/lexical encoding, just as it precedes native text embedding.

## 8.3 MemorySpace hierarchy

The current adapter plan groups normal 30-second clips into five-clip parent blocks:

```text
video
│
├─ block_000              # 5 adjacent clips ≈ 150 s
│  ├─ clip_000
│  ├─ clip_001
│  ├─ clip_002
│  ├─ clip_003
│  └─ clip_004
│
├─ block_001
│  └─ ...
```

Every searchable unit can retain:

```text
clip membership
block membership
memory_type membership
source M3 node provenance
```

These spaces are logical scopes/filters. The design does not require a separate vector database for every clip.

## 8.4 Entity-relation construction dependency

The adapter plan adds a searchable third text-memory type:

```text
entity_relation
```

Construction logic:

```text
M3 face/voice/character evidence
+
episodic/semantic text from one clip
        │
        ▼
relation-extraction LLM
(one construction call per clip in the adapter plan)
        │
        ├─ relation edge(s)
        └─ MemoryUnit(type=entity_relation)
```

Important boundary:

> This LLM may extract relations, but native M3 characters and scoped assignments remain authoritative. Identity consolidation is implemented upstream and is not delegated to relation extraction.

The generic adapter defaults to configured `gemini-3.8-flash-302`. The automatic consolidation deployment explicitly sets `build_relations=false`; its verified run made no relation-model calls. Reranking and graph expansion are optional retrieval arguments.

---

# 9. Mandol retrieval dependencies

The Mandol query path is a **hybrid retrieval system**, not a single cosine search.

## 9.1 Index preparation

Before query time, adapted MemoryUnits are prepared into shared search representations:

```text
MemoryUnit text
    │
    ├─ BM25 lexical representation/index
    │
    ├─ dense encoder → 1024-D dense vectors → shared dense/FAISS index
    │
    └─ SPLADE encoder → sparse vectors → shared sparse index
```

The adapter document explicitly describes shared dense/BM25/SPLADE indexes. It does not require rebuilding these representations for each query.

## 9.2 Query-time flow

```text
user query
   │
   ├───────────────┬────────────────┐
   ▼               ▼                ▼
BM25 search   1024-D dense      SPLADE sparse
                   search            search
   │               │                │
   └───────────────┴────────────────┘
                   │
                   ▼
             candidate fusion
                   │
          optional graph expansion
                   │
                   ▼
           optional reranker
                   │
                   ▼
              top-k evidence
```

All of those internal operations still sit behind **one application-level retrieval call**. No LLM controller is required to choose “BM25 versus dense versus sparse” for each query.

## 9.3 Mandol model dependency status

The current project-level dependency contract is:

| Mandol component | Required behavior | Exact model/checkpoint status in this repo |
| --- | --- | --- |
| BM25 | lexical candidate retrieval | no learned model required |
| Dense encoder | generate **1024-D** text vectors | Qwen3-Embedding-0.6B; current OpenRouter defaults versus recorded 302.AI cycle described below |
| Dense index | shared vector search, adapter plan names FAISS | algorithm/storage role pinned; deployment details may vary |
| Sparse encoder | SPLADE sparse representation | verified run: `naver/splade-cocondenser-ensembledistil` through local `naver/splade-v3` alias |
| Sparse index | search sparse representation | implementation detail not fully pinned |
| Fusion | merge lexical/dense/sparse candidates | M3 adapter retrieval uses reciprocal-rank fusion |
| Graph expansion | optionally use entity relation topology | structural operation, not necessarily learned |
| Reranker | reorder fused candidate pool | **exact reranker checkpoint not pinned** |
| Relation builder | optionally extract relations per clip | configured `gemini-3.8-flash-302` default; disabled in consolidation deployment |

Current Mandol source defaults to `qwen/qwen3-embedding-0.6b` at `https://openrouter.ai/api/v1` and resolves an OpenRouter credential. The retained `consolidation/deployment.json` and successful combined-cycle artifacts specify `Qwen/Qwen3-Embedding-0.6B` at `https://api.302.ai/v1`, using the then-deployed 302.AI adapter. That historical result does not validate today's credential resolver against the retained endpoint: deployment must align endpoint, model and credentials. The sparse model's local alias likewise does not establish v3 weights; saved metadata records the actual checkpoint source.

`M3MandolRetriever.load(session_directory)` checks `CURRENT.json` at query entry and switches to a verified newly published bundle. Each query pins one reader; explicit version paths remain pinned. Published Mandol files are copied to a temporary runtime directory before loading so cache/lock writes cannot mutate immutable artifacts. No person-based audit files are required for retrieval.

---

# 10. Native vs Mandol text encoders

This is a required architectural rule for the adapter.

## 10.1 Native M3

```text
text-embedding-3-large
3072-D
```

Stored directly on M3 episodic and semantic nodes and used for native query search.

## 10.2 Mandol

```text
Mandol dense encoder
1024-D
```

Stored in Mandol's own shared dense index.

## 10.3 Adapter consequence

Do **not** implement:

```text
M3 3072-D node vector
      ↓
insert directly into Mandol 1024-D index   ✗
```

The correct dependency flow is:

```text
M3 node text + provenance
      ↓
M3 → Mandol adapter
      ↓
Mandol MemoryUnit text
      ↓
Mandol encoding/index builder
      ├─ lexical/BM25
      ├─ 1024-D dense
      └─ SPLADE sparse
```

This makes the adapter a **semantic/provenance conversion layer**, while Mandol owns its retrieval encodings.

---

# 11. Native character consolidation and live runtime

Consolidation and automatic native/Mandol reindexing are implemented. The live runtime is an opt-in wrapper around that core: it preserves the existing prompt, evidence policy, deterministic executor and native application logic. Real saved-decision publication and deterministic concurrency tests are separate validation results.

## 11.1 What already exists

The construction pipeline already has two lower-level identity mechanisms:

```text
VOICE
CAM++ embedding
  → cosine threshold 0.6
  → voice node association

FACE
Buffalo-L embedding
  → HDBSCAN + quality filtering
  → cosine threshold 0.3
  → img node association
```

The selected VLM backend can then produce face↔voice equivalence statements, and legacy `refresh_equivalences()` turns those links into `character_N` mappings. Consolidated/runtime-managed graphs preserve established native identity state during refresh as described in section 5.3.

The standalone `tst/runner.py` can still score externally enrolled global speaker IDs from audio, but the online benchmark's `TSTVoiceMapper` attaches ECAPA vectors directly to native `voice_N` nodes. It does not create named global identities or bypass native `character_N` consolidation.

## 11.2 Fragmentation addressed by consolidation

Those operations do not guarantee a single stable person across a long stream.

Example failure:

```text
same physical person
   ├─ voice_31 in earlier clips
   ├─ voice_78 later
   ├─ face_4 in one scene
   └─ face_22 after appearance/camera changes
```

If upstream evidence never creates sufficient equivalence links, the current union-find layer cannot infer that all four observations belong to one person.

The implemented recall-oriented prompt infers likely cluster/person identities, propagates supported defaults, and records observation-level exceptions. It attempts most observations rather than requiring each utterance to independently prove a name. Confidence, rationale and evidence remain required; genuine conflicts and unsupported identities stay unresolved. No additional face detector or visual inference pipeline is introduced.

## 11.3 Inputs available to a consolidator

Without adding any new upstream sensing model, the repository already exposes useful evidence:

```text
CAM++ or ECAPA 192-D voice embeddings, depending on the construction condition
Buffalo-L face embeddings
ASR transcript + speaker-turn timestamps
VLM episodic memories
VLM semantic memories
existing Equivalence statements
character_mappings
clip/time provenance
embedding similarity values / matching history
```

The consolidation worker runs MOSS on exactly the interval from the previous successful identity cutoff to the current committed snapshot, before reasoning. Supplied MOSS output must match both window endpoints. Window-local model timestamps are converted to session time; old observations used as anchors are not retranscribed or marked unmatched. MOSS speaker labels are run-local evidence, not persistent identities; missing historical assignment scores remain unknown. Audio duration, parsing and interval checks protect the evidence horizon.

The benchmark calls `llm_consolidator.propose_official` with an explicit `gpt-5.6-sol` model override and high reasoning. The shared transport saves resumable response IDs and exact prompt/request/output artifacts. Sol receives the organized packet, including transcript/alignment evidence; this does not imply uploading the full raw waveform in that request. The transport's historical Astra default does not select the benchmark model. `patch_executor.execute` validates structured decisions, and `native.project` translates them into native character operations. Subsequent proposal state is reconstructed from current native characters, not previous person-based audit state.

## 11.4 Correct write-back boundary

A consolidation decision affects more than one dictionary.

```text
accepted identity consolidation
       │
       ├─ update canonical M3 character mapping / alias state
       ├─ preserve source face/voice evidence
       ├─ preserve provenance + confidence
       ├─ preserve raw contents; canonicalize separate retrieval text
       ├─ selectively re-embed changed native text nodes
       │
       └─ invalidate / refresh affected Mandol representation
              ├─ entities
              ├─ entity_relation units
              ├─ BM25 representation if text changed
              ├─ 1024-D dense vectors if text changed
              └─ SPLADE sparse vectors if text changed
```

A character merge must **not** concatenate incompatible embedding spaces or replace CAM++/Buffalo-L observations with a text vector.

### Offline complete-bundle publication

`pipeline.publish` → `native.publish_native` stages a copied native graph, accepted identity changes and selective text reindexing. `reindex_cycle.build_retrieval_bundle` exports canonical memory and invokes `mandol_worker` to rebuild dense, BM25 and SPLADE indexes. The worker reloads every memory/vector and checks hybrid retrieval before publication.

Native reindexing batches only changed canonical inputs and validates vector count, dimensions and finiteness before replacement. Unaffected text vectors and all native audio/face/image vectors remain unchanged. Mandol currently rebuilds its complete staged text/entity bundle rather than selectively modifying the previous index. Relations are disabled in the cycle configuration.

The version contains `graph.pkl`, review JSON, identity/embedding reports, supplied exact model artifacts, canonical `mandol_input/`, built `mandol/`, readiness receipts and recursive artifact hashes. Only then does `CURRENT.json` advance. Stale bases or embedding/index failures preserve the previous publication. This offline publication lock is separate from a live mutation lock; running the offline call synchronously on the clip writer would block construction.

## 11.5 Asynchronous streaming coordination

```text
normal ordered clip writer → LIVE VideoGraph → immediate native retrieval
                                  │
                         completed media cutoff
                                  ↓
                         frozen native snapshot
                                  ↓
                 evidence / Sol / existing executor
                                  ↓
                 staged native identity patch result
                                  ↓
              reconcile and commit between clip writes
                                  ↓
                 selective background native reindex
                                  ↓
          optional verified Mandol checkpoint publication
```

`ConsolidationRuntime` uses one sequential reasoning job and one background index job in a two-thread executor. There is one authoritative graph and one ordered construction writer. The runtime holds no graph-wide lock across clip processing, model calls or network embedding requests. Individual native mutations, snapshot copies and in-memory commits use short critical sections. Copying and canonical-text scans still scale with graph size; this is not a zero-pause or measured hard real-time guarantee.

At a completed clip boundary, `ConsolidationSnapshot` records the live integer graph revision, cutoff clip, exact media end timestamp and detached graph/edge/identity state. A clip-39 job does not acquire clips 40–45 or later raw-feature observations as construction continues. A worker modifying its input snapshot is rejected.

The default period is 1,200 media seconds. One active and one waiting snapshot preserve each completed boundary. When the waiting slot is full, the writer pauses before the next boundary-crossing clip until capacity becomes available. Queued snapshots receive preceding accepted identity updates with the live commit's ID remapping before their prompts are built. Scheduling uses committed media time, not nominal clip duration or wall time.

## 11.6 Atomic native identity reconciliation

`NativeConsolidationWorker` wraps the full evidence builder, compact prompt builder, configured proposal callable, scoped executor and `native.project`. New observations and memories enter the prompt with compact native characters and bounded original historical anchors; paths, duplicate evidence bodies, and prior decision prose stay internal. Defaults apply only to the new window; explicit historical corrections require visible evidence. Projection receives the complete resulting state. It returns `ConsolidationPatch(snapshot, graph)`, a native identity result bound to the historical snapshot. The original model patch/execution report remains a separate audit artifact. See [packet format and budgets](consolidation/INCREMENTAL.md).

The runtime validates cutoffs and node/edge integrity before commit. It rejects direct edits to raw node contents, metadata, vectors or edges. At commit it verifies the unchanged identity base and historical source; normal voice/face observation suffixes may have grown. `reconcile` combines the base, accepted result and current live identity state without replacing nodes, vectors, edges or temporal indexes.

Hot features assigned by construction to a merged native character inherit its survivor through the new authoritative mapping. This is not a historical fallback or `person_N` alias layer. Appends to an already reviewed raw feature instead invalidate completeness and use scoped admission. Concurrent hot character-ID allocations take precedence; colliding worker-local new IDs are remapped monotonically.

The resulting canonical representations are validated before native identity fields are committed. Watermarks distinguish hot and consolidated memory:

| Native runtime field | Meaning |
| --- | --- |
| `current_graph_version` | Live integer revision advanced by completed clips and identity commits |
| `last_completed_clip_id`, `last_completed_timestamp` | Latest completed construction boundary |
| `last_consolidated_clip_id`, `last_consolidated_timestamp` | Accepted historical identity boundary |
| `entity_registry_version` | Current native identity revision |
| `identity_revision` | Native character-state version |

The live revision is distinct from published `graph_version = v_<digest>`. Memory after the consolidation watermark is hot; both regions remain searchable in the same native graph.

## 11.7 Background reindexing and two readiness boundaries

Changed representations are marked `embedding_stale=True`. The index worker canonicalizes and re-embeds through the existing M3 backend. `identity_reindex_async` prevents native search and `prepare_texts` from synchronously catching up old entries; newly constructed text still receives its normal canonical embedding.

Until catch-up completes, old vectors remain searchable, so scores can temporarily reflect previous identity wording. Installation checks identity revision, raw contents and effective canonical text. Superseded results cannot overwrite newer identity state; a fresh pass is scheduled.

When configured, `RetrievalPublisher` builds/verifies a complete native/Mandol checkpoint in the background and records runtime watermarks in `runtime.json`. It never loads that old snapshot over the live graph. Live worker job directories separately preserve snapshot, evidence, patch and identity reports.

**Identity commit and index publication are distinct:** live native identity can change before embedding catch-up finishes, while the persisted retrieval pointer advances only after readiness checks succeed. Native live queries see hot memories immediately. A published Mandol checkpoint contains only its indexed snapshot; later hot arrivals are not automatically available through that persisted Mandol reader. No separate Mandol indexing timer is required for the consolidation cycle.

## 11.8 Deployment, persistence and retry

The application explicitly supplies an evidence callback, configured proposal callable and optional `RetrievalPublisher`, then attaches `ConsolidationRuntime` to its native graph. The shared `process_segment` wrapper participates automatically when attached and requires `sample['segment_end_s']` from the scheduler. Other entry points wrap their existing writer call in `runtime.segment(clip_id, end_seconds)`. Mutation outside that single-writer contract is not coordinated streaming.

The reusable online services are owned by the original M3 package: `PreparedASRCache` performs one content-addressed provider call per audio payload, `export_consolidation_evidence` exports a committed prefix, and `GraphCheckpointStore` owns transactional graph checkpoints plus immutable cutoff snapshots. The benchmark keeps only thin adapters around these services.

The online benchmark uses the higher-level `consolidation.port.attach_online`
interface and `consolidate_until(cutoff)` to synchronize C1-C4 boundaries. Scheduling,
model transport, MOSS, timing and native reindexing are implemented and debugged in
the shared consolidation package. The benchmark supplies committed evidence and
records returned results; it does not subclass or call private runtime methods.

Model/evidence or patch-validation failure leaves identity and watermark unchanged while construction continues. `runtime.errors` records failures; `runtime.retry()` retries retained failed work when idle. Index failures retain old vectors and the prior publication; they can retry explicitly or at the next completed clip without a tight failure loop.

Runtime objects, locks and executors are excluded from pickles; native identity/watermarks persist. Attach a new runtime after loading a checkpoint. `close()` drains ordered work and a remaining final interval at stream shutdown, never within a clip; retained failures raise a retry-required error. Failed reasoning windows retain their slot and block later windows until explicit retry. Retry scheduling is process-local, not a durable distributed queue. The runtime does not silently provision models, install an evidence collector or enable paid API calls.

See [runtime wiring and contract](consolidation/RUNTIME.md) and [automatic reindexing](consolidation/AUTOMATIC_REINDEX.md).

## 11.9 Verified results and validation limits

The selected native fixture reuses accepted **20-minute recall round-1** decisions and the original checkpoint, initializing its missing mappings with the existing M3 routine. No new Astra call was needed. It verified four supported native identities (Jake, Xiu Shuo and two unnamed), 216 observation assignments, 87 safe features, 19 mixed/incomplete features and 43 explicit reference occurrences.

The combined cycle re-embedded 105 of 383 native text nodes and preserved 278 text plus all 106 voice embedding collections. Raw contents/edges were unchanged. Mandol verified all 383 memories with dense/BM25/SPLADE and successful hybrid/published-reader probes. The successful version is `v_66eb04de45183ff45dd782fdfb306defbbc592fc4b50113983c2c626420e53d7`. Its first missing-SPLADE-path attempt published nothing; the repaired run exited 0. Face behavior is covered by synthetic fixtures because the real fixture has no face nodes. The stopped 40-minute work has no validated published graph.

Native architecture tests cover merges, partial moves, scoped precedence, mixed fallback, strict majority admission, refresh/reload, selective reindexing, incremental history preservation and reference correction after reload. Runtime tests cover continued hot construction/retrieval, frozen snapshots, cutoff rejection, failure/retry, hot identity inheritance, ordered windows, backpressure, queued identity rebasing, final draining, boundary commits, concurrent ID allocation and superseded-index rejection. These deterministic checks do not establish sustained hosted streaming performance or independent identity accuracy.

Artifacts: [native integration](consolidation/NATIVE_CHARACTER_INTEGRATION.md), [combined-cycle replay and hashes](consolidation/runs/deployment_cycle/README.md), and [runtime tests](consolidation/tests/test_runtime.py). Shared GPU/network contention and snapshot/commit latency still require deployment measurement. The current provider/configuration distinction in section 9.3 must be resolved before repeating the historical cycle with current Mandol source.

---

# 12. Runtime package dependencies

Current `StreamMeCo/requirements.txt` contains the core Python requirements:

```text
opencv-python-headless
pillow
matplotlib
pydub
scikit-learn
tqdm
openai
moviepy
httpx
insightface==0.7.3
onnxruntime-gpu>=1.21,<2
hdbscan>=0.8.40
qwen-vl-utils>=0.0.14
av>=14,<16
torch>=2.6
torchaudio>=2.6
transformers>=5.0
accelerate>=1.10
pydantic>=2.9,<3
```

SpeakerLab is also required by the CAM++ path and is provided from the 3D-Speaker source tree in the deployment runbook.

The **separate** TST environment is declared in `tst/requirements.txt`: `numpy`, `scipy`, `soundfile`, `torch`, `torchaudio`, `speechbrain`, `huggingface_hub`, and `PyYAML` (for YAML configuration). Install it independently of the production construction requirements. TST needs prepared audio and manifests; it does not require SpeakerLab/CAM++, Deepgram or MAI API access during mapping, Buffalo-L, Qwen, the text-embedding API, Mandol, or a GPU. CPU and CUDA devices are supported. The pinned SpeechBrain snapshot must be locally available for `offline: true`; otherwise model acquisition can access Hugging Face. This package list has no claimed known-good version matrix for the production GPU environment below.

Native identity resolution itself uses the standard library and does not import consolidation. Native graph loading uses lazy imports rather than initializing perception models. Native consolidation dependencies are listed in `consolidation/requirements-native.txt`. The verified combined cycle used a separate Python 3.12 Mandol environment selected by `MANDOL_PYTHON`; its working directory must resolve the installed sparse checkpoint.

## 12.1 Known-good GPU environment recorded in the repo

`HYPERSTACK_GPU_RUNBOOK.md` records the following successful reference environment:

| Dependency | Recorded version |
| --- | --- |
| Python | 3.10.8 |
| PyTorch | 2.6.0+cu124 |
| torchvision | 0.21.0 |
| torchaudio | 2.6.0+cu124 |
| transformers | 5.17.0 |
| accelerate | 1.15.0 |
| ONNX Runtime GPU | 1.21.1 |
| InsightFace | 0.7.3 |
| OpenCV headless | 4.11.0.86 |
| NumPy | 1.26.4 |
| SciPy | 1.14.1 |
| MoviePy | 2.2.1 |
| OpenAI client | 1.109.1 |
| HTTPX | 0.28.1 |
| FLA core | 0.5.2 |
| scikit-learn | 1.6.1 in the runbook install command |
| HDBSCAN | 0.8.44 in the runbook install command |

This table is a **recorded working environment**, not a claim that every version is the minimum supported version.

## 12.2 Native system dependencies

```text
NVIDIA driver compatible with CUDA environment
ffmpeg
ffprobe
git / git-lfs for setup
CUDAExecutionProvider for ONNX Runtime
```

The runbook targets a CUDA-capable GPU with at least 24 GB VRAM for the full local Qwen/Buffalo-L/CAM++ construction pipeline.

---

# 13. Model assets and environment variables

## 13.1 Local model assets

```text
models/Qwen3.5-4B/
models/camplus/.../campplus_cn_en_common.pt
models/insightface/models/buffalo_l/
```

The runbook specifically verifies Buffalo-L detection and recognition ONNX files and the CAM++ checkpoint.

TST does not use those model paths. Its `speechbrain/spkrec-ecapa-voxceleb` revision must be an immutable commit in the run configuration. The runner records checkpoint/preprocessing hashes and package versions and stores ECAPA embeddings under its own cache directory. AS-Norm additionally requires the supplied cohort manifest/audio; no VoxBlink2 cohort is bundled in the repository.

## 13.2 Model-path environment variables

```bash
QWEN_MODEL_PATH
CAMPLUS_CHECKPOINT
INSIGHTFACE_MODEL_ROOT
```

These override the default paths in `processing_config.json`.

TST uses the encoder revision, device, and cache directory in its own run configuration, not the production `CAMPLUS_CHECKPOINT` override.

## 13.3 API credentials

Core construction/retrieval API credentials include the key for the selected ASR alias:

```bash
DEEPGRAM_API_KEY
OPENROUTER_API_KEY
```

The repository also references:

```bash
API_302_KEY
```

for the Gemini comparison and configured 302.AI integrations, including the recorded Mandol cycle. Current Mandol dense defaults resolve an OpenRouter credential instead (section 9.3). Official Terra and Sol use the benchmark's API-config environment credential references. Credentials are never part of public build settings or review artifacts.

The OpenAI-compatible text-embedding client additionally depends on the provider mapping/credentials configured for `text-embedding-3-large` in runtime API configuration.

---

# 14. Configuration files and what they control

## `StreamMeCo/configs/processing_config.json`

Controls high-level runtime and model selection, including:

```text
30 s clip interval
frame sampling
single ASR provider alias
CAM++ checkpoint
Buffalo-L model/root
Qwen model path
face thresholds
minimum audio duration
Qwen video sampling / token settings
legacy controller-related flags
```

## `StreamMeCo/configs/memory_config.json`

Controls graph identity matching and retained embedding counts:

```text
max_img_embeddings      = 10
max_audio_embeddings    = 20
img_matching_threshold  = 0.3
audio_matching_threshold= 0.6
```

## `StreamMeCo/configs/api_config.json`

Loaded by API utilities to map provider aliases to OpenAI-compatible/API settings. Treat it as deployment configuration; credentials should not be committed.

## `mandoladaptor.md`

Defines the current Mandol mapping and retrieval contract, including:

```text
MemoryUnit mapping
5-clip parent MemorySpaces
EntityRegistry
entity_relation units
shared dense/FAISS + BM25 + SPLADE indexes
hybrid retrieval + reranker
```

## `consolidation/deployment.json` and runtime settings

The public deployment file selects Mandol encoder, endpoint, dimension, batching and relation/sparse options; `CONSOLIDATION_DEPLOYMENT_CONFIG` can replace it. `MANDOL_PYTHON` selects the worker interpreter and `MANDOL_WORKDIR` its local model lookup directory. Provider/model/credential selections must agree with the current adapter and saved index manifest.

`ConsolidationRuntime` explicitly receives evidence/proposal callbacks, a default 1,200-second period, configured or test embedder, and optional `RetrievalPublisher`. Loading a graph does not enable it. The scheduler supplies exact clip end time through `sample['segment_end_s']` or `runtime.segment(...)`.

---

# 15. End-to-end dependency DAG

This is the most explicit view of what must exist before each stage can run.

```text
video/audio ──► decode ──► audio ───────────────┐
                                                 ▼
                                         ┌─────────────────────┐
                                         │ selected ASR alias  │
                                         │ Deepgram OR MAI     │
                                         │ or supported adapter│
                                         └────────┬────────────┘
                                                  │ transcript / turns
                              ┌───────────────────┴───────────────────┐
                              ▼                                       ▼
                    ┌─────────────────────┐                 ┌─────────────────────┐
                    │ CAM++ / CAMPPlus    │                 │ SpeechBrain ECAPA   │
                    │ C1                  │                 │ C2/C3/C4, TST       │
                    │ 16 kHz → 192-D      │                 │ 16 kHz → 192-D      │
                    └────────┬────────────┘                 └────────┬────────────┘
                             └───────────────────┬───────────────────┘
                                                 ▼
                                      native M3 voice search
                                      match/update or create
                                                 │
                                             voice nodes

video ──► frames ──► Buffalo-L detection + recognition ──► HDBSCAN ──► img nodes
   │                                                                       │
   │                                                                       │
   └───────────────────────────────┬───────────────────────────────────────┘
                                   │
                                   ▼
                           configured VLM backend
                    video + face IDs + voice IDs/ASR
                                   │
                      ┌────────────┴────────────┐
                      ▼                         ▼
                episodic text             semantic text
                      │                         │
                      └────────────┬────────────┘
                                   ▼
                      native canonical retrieval text
                                   │
                                   ▼
                      text-embedding-3-large
                              3072-D
                                   │
                                   ▼
                              VideoGraph
                   ┌───────────────┼────────────────┐
                   │               │                │
                   │               │                └─ equivalence semantic nodes
                   │               │                         │
                   │               │                         ▼
                   │               │                 union-find character mapping
                   │               │
                   │               └─ optional StreamMeCo compression
                   │                         no new model
                   │
                   ├──────────────────────────────────────────────┐
                   │                                              │
                   ▼                                              ▼
          Path A: native                                 Path B: Mandol
                   │                                              │
query ─► text-embedding-3-large                  M3→Mandol adapter
          3072-D                                     │
                   │                                  ├─ episodic → MemoryUnit
                   ▼                                  ├─ semantic → MemoryUnit
           cosine text search                         ├─ character → entity
                   │                                  └─ relation LLM → entity_relation
                   ▼                                              │
             clip aggregation                                     ▼
                   │                                  Mandol representation build
                   ▼                                  ├─ BM25
              ranked evidence                         ├─ 1024-D dense encoder/index
                                                      └─ SPLADE sparse encoder/index
                                                                 │
query ────────────────────────────────────────────────────────────▼
                                               BM25 + dense + sparse
                                                         │
                                                    fusion / graph
                                                         │
                                                 optional reranker
                                                         │
                                                         ▼
                                                   ranked evidence
```

---

# 16. Initialization order

A clean runtime should initialize dependencies in roughly this order.

For live consolidation, attach the runtime before the ordered clip loop and supply the existing evidence/proposal adapters. Reasoning operates on detached snapshots, identity commits occur between clip writes, and reindexing runs in the background. The growing native graph must never be replaced by a published historical checkpoint. See section 11 for the consolidation branch of the dependency DAG above.

## Construction worker

```text
1. load processing_config + memory_config
2. validate API credentials
3. select the speaker frontend: CAM++ for C1 or ECAPA/TST for C2/C3/C4
4. initialize / lazily load the selected speaker frontend
5. initialize / lazily load Buffalo-L via ONNX Runtime GPU
6. initialize the configured VLM backend
7. initialize API client for text embeddings
8. process clips into VideoGraph
9. refresh character equivalences
10. optionally compress graph
11. serialize graph
```

## Standalone frozen-enrollment TST utility (separate)

```text
1. validate selected-provider segment provenance, verified enrollment, configuration, and optional cohort manifests
2. load the exact SpeechBrain ECAPA snapshot on CPU or CUDA
3. extract/cache enrollment (and, for AS-Norm, cohort) embeddings
4. extract query embeddings; optionally compensate short queries within one diarization session
5. pool per-window-pair scores over the declared gallery
6. emit score-only or calibrated open-set decisions plus run provenance
```

This utility does not load a VideoGraph or perform construction/retrieval steps above or below it. Its `offline` flag controls local model loading only; the online benchmark uses `TSTVoiceMapper` instead.

## Native retrieval worker

Native retrieval does not need all construction models resident in memory:

```text
1. load serialized VideoGraph
2. initialize text-embedding API client
3. receive query
4. embed query with text-embedding-3-large
5. cosine search / clip aggregation
6. return evidence
```

Therefore a native retrieval-only process does **not** need Qwen, CAM++, Buffalo-L, Deepgram, or MAI loaded after the graph already exists.

## Mandol retrieval worker

```text
OFFLINE / REFRESH
1. load selected M3 graph
2. adapt nodes/entities/spaces
3. run relation builder where required
4. build BM25 representation
5. encode 1024-D dense vectors and build dense index
6. encode SPLADE sparse vectors and build sparse index
7. initialize reranker if configured

QUERY TIME
8. receive query
9. create lexical/dense/sparse query representations
10. retrieve candidates
11. fuse / optional graph expansion
12. rerank if configured
13. return evidence
```

This separation is important for latency measurement: model/index construction is not query latency.

---

# 17. Legacy dependencies that are not required by the new direct path

The repository still carries original M3-Agent compatibility and controller assets, including references to:

```text
StreamMeCo/models/M3-Agent-Control/
StreamMeCo/models/M3-Agent-Memorization/
```

and configuration fields such as:

```text
planning
route_switch
max_retrieval_steps
api_chat_model
```

Those remain relevant for reproducing the original M3 controller pipeline, but **M3-StreamConative's target direct retrieval path does not require M3-Agent-Control**.

Similarly, `memorization_memory_graphs.py` selects the configured VLM backend through `mmagent.memory_backend`; the online benchmark selects Terra, while Qwen and Gemini remain available as alternate implementations.

This distinction prevents the dependency list from overstating what a simple construction + one-shot retrieval deployment actually needs.

---

# 18. Failure boundaries and stale-state risks

## ASR failure

If the selected ASR provider fails, voice segmentation/identity evidence may be missing or partial. That propagates to the VLM because the backend receives fewer or lower-quality `<voice_ID>` observations. Provider failure does not implicitly select another ASR branch.

## CAM++ mismatch

If the same speaker falls below the `0.6` voice-match threshold, a new voice node can be created. This is a major input to persistent identity fragmentation.

## Standalone TST input/calibration failure

The standalone frozen-enrollment utility fails validation if a required cohort, immutable encoder revision, or declared gallery is missing; it never falls back to CAM++ or a smaller strict cohort. The online TST mapper has no gallery or calibration requirement: it uses the current graph's native threshold and creates a voice node when no existing node matches.

## Buffalo-L / face-quality failure

If no face passes detection/quality/clustering, the VLM receives no usable face identity label for that person in the clip.

## VLM identity omission

Even if a face and voice belong to the same person, `refresh_equivalences()` cannot merge them unless sufficient equivalence evidence reaches the graph. Union-find itself cannot infer missing edges.

## Text-embedding provider failure

Construction cannot create searchable episodic/semantic vectors, and native query retrieval cannot produce a compatible query vector.

## Compression stale index

If the graph is compressed **after** Mandol indexes are built, Mandol may retrieve content that no longer exists in the selected M3 memory. Build/refresh Mandol after compression.

## Character consolidation stale index

Consolidation preserves raw text and changes its separate canonical retrieval representation. Offline publication completes selective native reindexing and a full staged Mandol build before advancing the pointer. Live runtime commits identity first, retains searchable old vectors while background reindexing runs, and checks revision/content before installation. Failed builds leave the previous persisted index current. Live native queries include hot memories; a persisted Mandol checkpoint does not automatically include later arrivals.

## Concurrent construction or historical-source changes

The runtime requires one ordered clip writer. Model work holds no live mutation lock, and identity commits wait for a clip boundary. Historical node removal/source changes or an incompatible identity revision reject the patch; replacing the live graph with a snapshot is never the commit strategy. Model failures leave identity/watermarks unchanged. Index failures remain retryable. Snapshot-copy cost and shared inference resources still require deployment latency measurement.

---

# 19. Recommended experiment dependency matrix

This table makes it explicit which dependencies should be running for each experiment.

| Experiment | Selected ASR | Speaker frontend | Buffalo-L | VLM backend | M3 text embedding | StreamMeCo | Mandol encoders/index | Reranker | Controller |
| --- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| Build fresh M3 memory | ✓ | CAM++ or ECAPA/TST | ✓ | configured backend | ✓ | – | – | – | – |
| Build + compress | ✓ | CAM++ or ECAPA/TST | ✓ | configured backend | ✓ | ✓ | – | – | – |
| Query existing graph, native | – | – | – | – | ✓ | – | – | – | **No** |
| Query existing compressed graph, native | – | – | – | – | ✓ | already done | – | – | **No** |
| Build Mandol representation from existing graph | – | – | – | relation builder only if enabled | – for M3 native vectors | optional pre-step | ✓ | optional | **No** |
| Query Mandol representation | – | – | – | – | – | – | ✓ | optional | **No** |
| Character/entity consolidation | construction continues independently | stored evidence | stored evidence when available | Sol reasoning is separate from construction VLM | changed canonical text only | coordinate separately | staged rebuild for publication | optional | **No requirement** |

A dash means that model/service does not need to be invoked at that stage if its output has already been persisted.

The online TST condition is part of construction for C2/C3/C4: it consumes each selected-ASR utterance, generates ECAPA vectors, and writes through native M3 voice-node matching. The standalone frozen-enrollment TST utility remains a separate experiment with its own enrollment/cohort contract and is not evidence about the online graph policy.

---

# 20. Architectural invariants

The implementation should preserve these rules as the project evolves:

1. **M3 remains the canonical multimodal memory.** Mandol is a derived retrieval representation.
2. **Modality and encoder embeddings remain separate.** CAM++ and ECAPA speaker vectors, Buffalo-L face, M3 native text, and Mandol text embeddings must never be treated as one shared vector space; CAM++ and ECAPA are incompatible even though both are 192-D.
3. **Compression is optional and model-free.** It consumes existing graph embeddings.
4. **Native direct retrieval uses the same text embedding family as M3 text-memory construction.**
5. **Mandol owns its own search encodings.** The adapter passes text/provenance, not M3's incompatible 3072-D vectors as 1024-D Mandol vectors.
6. **No controller is required by either target retrieval path.** Hybrid retrieval can be internally complex while remaining one retrieval call.
7. **Identity evidence and identity decisions are distinct.** Face/voice vectors are evidence; native `character_N` plus scoped assignments are authoritative. Consolidation updates that state; `person_N` is proposal/audit information only.
8. **Every derived representation should retain source provenance.** A Mandol MemoryUnit should be traceable to M3 node/clip/time evidence.
9. **Canonicalization precedes embedding.** Raw memory remains unchanged; selective native reindexing and verified Mandol publication are part of the consolidation cycle.
10. **Model provenance and provider configuration remain explicit.** Current defaults, the recorded deployment, and local checkpoint aliases are distinct; section 9.3 records the known Mandol configuration difference.
11. **Online TST uses native graph identity formation.** It has no pre-enrollment or fixed gallery; it creates/updates `voice_N` nodes in each C2/C3/C4 graph using ECAPA vectors, never mixing those vectors with CAM++ storage. The standalone `tst/runner.py` remains frozen-enrollment and graph-independent.
12. **Resolution is scoped-first.** Observation, reference occurrence, current global ownership, then raw ID; mixed/incomplete features cannot acquire an unsafe unscoped name.
13. **Historical refinement preserves live construction.** Snapshot workers cannot directly edit post-cutoff nodes or replace the growing graph. Native identity commits occur between clip writes, with model/index work outside the mutation path.
14. **Identity commit and retrieval publication have separate readiness boundaries.** Old vectors remain usable during live catch-up; stale results cannot overwrite newer identity state and incomplete index bundles cannot become current.
15. **History is versioned.** Refresh/reload preserve lineage and scoped decisions; earlier-cutoff queries require appropriate historical identity evidence.

---

# 21. Key repository references

The architecture above is grounded in these repository files:

```text
StreamMeCo/configs/processing_config.json
StreamMeCo/configs/memory_config.json
StreamMeCo/requirements.txt

StreamMeCo/m3_agent/memorization_memory_graphs.py

StreamMeCo/mmagent/voice_processing.py
StreamMeCo/mmagent/face_processing.py
StreamMeCo/mmagent/src/face_clustering.py
StreamMeCo/mmagent/memory_processing_qwen.py
StreamMeCo/mmagent/utils/chat_qwen.py
StreamMeCo/mmagent/utils/chat_api.py
StreamMeCo/mmagent/videograph.py
StreamMeCo/mmagent/retrieve.py

StreamMeCo/mmagent/character_identity.py
StreamMeCo/m3_agent/export_mandol.py
consolidation/native.py
consolidation/runtime.py
consolidation/runtime_io.py
consolidation/patch_executor.py
consolidation/prompts/system.md
consolidation/reindex_cycle.py
consolidation/mandol_worker.py
consolidation/deployment.json
consolidation/RUNTIME.md
consolidation/NATIVE_CHARACTER_INTEGRATION.md
consolidation/AUTOMATIC_REINDEX.md
consolidation/tests/test_runtime.py
Mandol/src/mandol/adapters/m3/adapter.py
Mandol/src/mandol/adapters/m3/retriever.py

StreamMeCo/streammeco.py
tst/README.md
tst/requirements.txt
tst/runner.py
tst/audio.py
tst/encoder.py
tst/scoring.py
benchmark/aea_6h/tests/test_tst.py
TST_ALGORITHM_SPEC.md
mandoladaptor.md
GPU_PIPELINE_REQUIREMENTS.md
HYPERSTACK_GPU_RUNBOOK.md
```

These references should be updated alongside this document when a model checkpoint, vector dimension, provider, threshold, or retrieval backend changes.
