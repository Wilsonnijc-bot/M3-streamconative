# TST speaker identity mapping — algorithm specification

Status: implemented as a separate offline runner; no benchmark results claimed.

Encoder decision: use a standard pretrained ECAPA-TDNN rather than requiring the paper's exact checkpoint. This changes only the encoder requirement; all other algorithm settings and the unchanged CAM++ baseline remain as specified below.

Source: Minjae Lee et al., [Who Spoke When in Multi-Conversation: Target Speaker Tagging Task and Benchmark, arXiv:2606.14091v1](https://arxiv.org/pdf/2606.14091v1), 12 June 2026. Reviewed 17 September 2026. Section and page references below refer to this version.

## 1. Objective and evidence labels

Build a separate audio-only reproduction of the speaker identity-mapping stage, keeping M3's CAM++ implementation available unchanged. Inputs are diarization from exactly one declared provider per run and externally supplied enrollment audio. Outputs associate each speech segment with an enrolled global speaker ID or `non_target`.

This specification distinguishes:

- **Paper:** details explicitly stated in the source.
- **Project requirement:** behavior requested for this repository, including the supplied task specification.
- **Reproduction choice:** a concrete implementation convention where the paper does not provide enough detail. These choices are versioned and must not be described as verified author behavior.

Scope ends at audio-to-identity mapping. Text embeddings, VLM calls, face identity, memory construction, retrieval, and automatic enrollment of unknown people are excluded. Transcript text is pass-through metadata and must not influence identification or enrollment selection automatically.

Implement first. Later, rerun CAM++ and the new mapper using the user's existing identity labels. Do not fabricate a results table or replacement recommendation before that evaluation.

## 2. Source-grounded requirements

| Topic | Paper requirement | Source |
| --- | --- | --- |
| Identity decision | Highest-scoring enrolled identity if its score reaches the threshold; otherwise non-target | §3.3; §5.1, Eq. 1 |
| Session gallery | Users specify the enrolled speakers expected in a session | §3.1; §5.2 |
| Encoder | ECAPA-TDNN, trained on VoxCeleb1/2, 256-dimensional embeddings | §6.2, p. 6 |
| Extraction | 4-second windows, 1.5-second shift | §6.2 |
| Scoring | Cosine, AS-Norm, and score-level average pooling for multiple embeddings | §6.2 |
| Cohort | Utterances from 2,000 randomly selected VoxBlink2 speakers; adaptation size 20 | §6.2 |
| Compensation | Combine embeddings from acoustically similar segments with the same diarization label; compare top-1/2/3 | §3.3; §7.1, Table 7 |
| Enrollment | TST-Bench: approximately 20 seconds per speaker; ICSI: ten longest utterances per selected session, up to two sessions | §4.2; §6.1 |
| Evaluation anchors | Non-overlapping reference speech ≥1 second; transfer prediction from the system segment with longest overlap; missed targets remain in the denominator | §5.2 |

The source does not fully specify checkpoint identity, preprocessing, window tails, cohort aggregation, compensation arithmetic, or threshold calibration. The following executable conventions are project choices, not additional claims about the paper. [Source PDF](https://arxiv.org/pdf/2606.14091v1).

## 3. Boundary with the existing repository

The following are inspected implementation facts, not paper requirements. Paths are relative to the repository root.

| Existing code | Current responsibility | Reproduction boundary |
| --- | --- | --- |
| `StreamMeCo/mmagent/voice_processing.py`: `process_voices()` and nested `diarize_audio()` / `get_audio_segments()` | Selected-ASR consumption, duration filtering, WAV slicing, caching, graph updates | Reuse compatible decoding/slicing behavior without invoking graph mutation |
| Same file: `_get_embedding_model()`, `get_embedding()`, `generate()`, `get_audio_embeddings()` | CAM++ loading and extraction; 192-dimensional embeddings; 16 kHz resampling; first-channel selection; CUDA execution | Preserve as the baseline; never feed ECAPA vectors into its caches |
| `StreamMeCo/mmagent/utils/chat_api.py`: `_normalize_transcription()`, `_segments_from_words()` | Provider normalization; historical `merge_primary_transcriptions()` remains unused by construction | Experimental input must retain the selected provider's provenance |
| `StreamMeCo/mmagent/videograph.py`: `search_voice_nodes()` | Mean pairwise cosine against each voice node's stored embeddings, followed by threshold and descending ranking | Existing CAM++ scoring reference |
| Same file: `add_voice_node()`, `update_node()` | Voice creation and bounded embedding history; updates randomly subsample when capacity is exceeded | Leave unchanged; no experimental writes |
| Same file: `refresh_equivalences()`, `order_character()` | Character mappings and reverse mappings | Leave unchanged; global enrollment IDs are supplied externally |
| `StreamMeCo/m3_agent/memorization_intermediate_outputs.py`: `process_segment()` | Calls the voice pipeline | No integration change in this audio-only implementation |

Important observed differences from the original task shorthand:

- Current `audio_matching_threshold` is **0.6**, both in `configs/memory_config.json` and the `VideoGraph` constructor default. It is not 0.7.
- `configs/processing_config.json` sets `min_duration_for_audio` to **2 seconds**. Preserve that baseline behavior; do not silently apply it to all TST inputs.
- Production voice processing selects Deepgram **or** MAI (or another supported transcription alias), invokes only that provider, and records its provenance; historical merged caches are not valid input to a new run.
- Current transcription normalization rounds timestamps to whole seconds. Preserve precise raw provider timestamps when available in prepared TST manifests; otherwise flag rounded input. Never imply lost precision was recovered.
- Production CAM++ creates new nodes on unmatched speech. The experimental known-speaker mapper returns `non_target`; it does not reproduce online identity discovery.

Avoid calling `process_voices()` wholesale from the new runner. It performs operations outside this experiment's boundary. Extract a small shared pure utility only if necessary and cover unchanged baseline behavior with a regression check.

## 4. Inputs, outputs, and invariants

### 4.1 Inputs

The runner accepts four independent manifests:

1. **Segments:** `session_id`, `clip_id`, `segment_id`, `audio_path`, `start_s`, `end_s`, `local_speaker_id`, optional `transcript`, and `diarization_provenance` matching the selected `diarization_provider`. Timestamps are relative to the referenced audio file. IDs must be unique within the run.
2. **Enrollment:** stable `global_speaker_id` plus one or more reference audio intervals, with source IDs and verification provenance. Aim for approximately 20 seconds of clean speech per person for the project experiment. Retain the enrollment utterance boundaries.
3. **Cohort:** source corpus, speaker IDs, utterance references, sampling seed, and checksums. Cohort IDs are never candidate output identities.
4. **Configuration:** one `diarization_provider` alias, encoder and preprocessing specification, scoring settings, compensation settings, candidate-gallery policy, optional threshold, and device.

An optional per-session list of enrolled IDs restricts candidate search. Support `session_subset` and `all_enrolled` as explicitly named gallery policies. Project default: `all_enrolled`, because future cross-clip recognition may not know attendance. This is a declared adaptation from the source-grounded session-gallery setting. Do not infer attendance from held-out truth.

### 4.2 Output

Emit one JSONL record per input segment, preserving IDs, times, transcript, and local label. Add:

```text
status: mapped | scored_only | invalid_audio | invalid_embedding | empty_gallery
predicted_global_speaker_id: enrolled ID | non_target | null
best_candidate_id: enrolled ID | null
best_score: finite number | null
threshold: finite number | null
candidate_scores: {global_speaker_id: score}
compensation_neighbor_ids: [segment_id, ...]
short_audio_flag: boolean (true for segments shorter than 1 second)
query_window_count, effective_embedding_count
method_id, gallery_id, cohort_id, encoder_fingerprint
timing_ms: embedding, compensation, scoring, mapping_total
```

`non_target` means a valid scoring decision rejected the available candidates. Invalid inputs are errors, not unknown-speaker predictions. An empty gallery is reported separately. Score-only mode produces scores with a null prediction. A segment shorter than 1 second remains eligible for scoring if its embedding is valid, but is flagged separately as less reliable; the flag is not a rejection decision.

### 4.3 Invariants

- Never compare embeddings from different encoders, preprocessing versions, or dimensions.
- Require one selected diarization provider per run, preserve it on each segment, and bind the method ID (and calibrated threshold artifact) to that provider.
- Enrollment remains fixed during a run; predictions never update enrollment.
- A local speaker label has meaning only within the diarization invocation that produced it. Default `session_id` to that invocation, usually one clip. Do not join identical numeric labels across clips.
- Compensation may use other segments within that session, including later segments. This is offline session processing; do not claim streaming-causal latency.
- Missing local labels disable compensation for that query; they do not form a shared null-label cluster.
- Unknown speakers remain unassigned to persistent identities.

## 5. Audio preparation and embedding extraction

**Reproduction choices:**

1. Validate finite times with `0 <= start_s < end_s <= audio_duration`. Convert to sample indices using floor for the start and ceil for the end, clamping only sample-rounding excess at the file boundary. Reject genuinely out-of-range intervals.
2. Decode once per file. Select the first audio channel to match the inspected baseline convention, resample to 16 kHz with a recorded backend/version, and crop using the validated timestamps. No denoising, extra VAD, or boundary expansion in the default comparison.
3. Use the encoder checkpoint's required feature extraction and waveform normalization. Record sample rate, feature settings, minimum accepted length, padding, checkpoint hash, package versions, and inference device. Disable training-time augmentation and dropout.
4. Reject non-finite or zero-norm model outputs. L2-normalize valid embeddings.

Let `L = 64,000` samples and `H = 24,000` samples at 16 kHz. For a crop of `T` samples:

- If the original interval is shorter than 1 second, flag it as less reliable in the segment output. Attempt extraction using the whole crop once; a valid embedding may still be scored. Do not treat this flag as `non_target` or `invalid_audio`.
- For `T <= L` (up to and including 4 seconds), encode the entire crop once. Do not stretch or repeat speech to manufacture four seconds. If the encoder requires a larger minimum input, right-pad zeros only to that minimum and record the padding.
- For `L < T <= L+H` (over 4 through 5.5 seconds), emit the start window `[0,L)` and end-aligned window `[T-L,T)`, exactly twice.
- For `T > L+H` (over 5.5 seconds), emit all full windows starting at `0, H, 2H, ... <= T-L`. Add a window starting at `T-L` if that exact start was not already emitted. Never duplicate the last window.

The end-aligned tail policy and short-input policy are reproduction choices. Preserve all resulting vectors for ordinary scoring; do not average them into a single enrollment or query vector by default.

Use **SpeechBrain `speechbrain/spkrec-ecapa-voxceleb`** as the standard pretrained ECAPA-TDNN. It accepts 16 kHz single-channel audio and produces native 192-dimensional embeddings. Use the same resolved checkpoint and preprocessing for enrollment, query, and cohort audio, then L2-normalize the embeddings. This is the intended project encoder, not a fallback pending access to the paper's model. [Model card](https://huggingface.co/speechbrain/spkrec-ecapa-voxceleb), [model configuration](https://huggingface.co/speechbrain/spkrec-ecapa-voxceleb/blob/main/hyperparams.yaml).

Record the exact resolved model revision, checkpoint hash, preprocessing configuration, and package versions for each run. Keep ECAPA caches separate from CAM++. Retain the model's native dimensionality; do not pad or project embeddings to match the paper's 256 dimensions. The source-grounded table in §2 describes the paper, not a requirement to obtain its checkpoint.

## 6. Gallery scoring and AS-Norm

This section makes the user's requested AS-Norm and score-pooling pipeline executable. The exact aggregation conventions below are reproduction choices.

### 6.1 Embedding sets

For enrolled speaker `g`, concatenate the window embeddings from its reference utterances into matrix `E_g` of shape `[m_g, d]`. Retain utterance/window metadata. Let query matrix `Q` have shape `[n, d]`. Rows are unit vectors.

Do not concatenate enrollment audio across disconnected intervals before windowing: that would introduce synthetic waveform boundaries. Every enrollment window receives equal weight, so longer references contribute more windows. This weighting is explicit and versioned.

### 6.2 Cohort construction

For the strict requested configuration, select exactly 2,000 distinct VoxBlink2 speakers using a stored seed. Require a source manifest with the actual chosen utterances. The paper does not specify utterance count or aggregation per cohort speaker.

Project convention: obtain window embeddings from all manifest-selected utterances for each cohort speaker; average those unit embeddings and L2-normalize the result to produce one centroid. Thus cohort matrix `C` has shape `[2000, d]`. This makes top-20 refer to distinct speakers rather than repeated windows from one speaker. Label this convention `speaker_centroid_v1`.

Never silently substitute another corpus, a smaller cohort, or a different centroid convention. An explicit approximate profile may do so, with a different fingerprint and fresh threshold calibration. Missing required assets must fail validation before mapping.

### 6.3 Standard symmetric adaptive normalization

For any unit embedding `v`, define:

```text
b(v)       = C @ v
t(v)       = 20 largest entries of b(v)
mu(v)      = mean(t(v))
sigma(v)   = sqrt(mean((t(v) - mu(v))**2))
sigma_e(v) = max(sigma(v), 1e-6)
```

Population standard deviation (`ddof=0`) and the epsilon are numerical conventions. Emit a diagnostic counter when the floor is used.

For enrollment embedding `e` and query embedding `q`:

```text
s(e,q) = dot(e,q)
a(e,q) = 0.5 * ((s(e,q) - mu(e)) / sigma_e(e)
              + (s(e,q) - mu(q)) / sigma_e(q))
```

Top-20 cohorts are selected independently for each side. Cache enrollment-side statistics, since both gallery and cohort are fixed. Recompute query statistics for a compensated query representation. AS-Norm scores are not probabilities and are not bounded to `[-1, 1]`.

### 6.4 Score-level pooling

```text
S_cos(g,Q) = sum(dot(E_g[i], Q[j]) for i,j) / (m_g * n)
S_asn(g,Q) = sum(a(E_g[i], Q[j])   for i,j) / (m_g * n)
```

Normalize each window-pair trial before pooling in the AS-Norm path. Do not replace this with cosine between mean vectors, normalization of an already pooled score, max pooling, or voting over window identities.

### 6.5 Open-set decision

Restrict scoring to the configured candidate gallery `G_session`. Resolve exact score ties by lexicographic global ID, giving deterministic output.

```text
g_star = argmax_g S(g,Q)
prediction = g_star if S(g_star,Q) >= theta else non_target
```

Require an explicitly supplied threshold for mapping. If it is absent, run score-only mode. Threshold artifacts must identify the encoder, cohort, gallery policy, compensation mode, and calibration data. Do not borrow 0.6 from CAM++ or the original prompt's 0.7 shorthand.

## 7. Local-label compensation: bounded, explicit approximation

The project supports `none`, `top1`, `top2`, and `top3`. Default is `none`; the full experimental profile selects `top3` explicitly. Whole-label identity assignment is excluded.

The source does not establish a precise short-duration cutoff, whether N includes the query, embedding weighting, a similarity floor, or how multi-window segments are combined. The following implements the previously agreed project approximation, named `short4_equal_segment_mean_v1`:

1. Compensate only queries shorter than 4.0 seconds. This cutoff is our choice, not a published setting.
2. Candidate neighbors have the same `(session_id, local_speaker_id)`, valid embeddings, and a different segment ID. No transcript, enrollment identity, or ground-truth label participates in selection.
3. Rank each neighbor `r` by mean pairwise raw cosine between its original window embeddings and the query's original window embeddings. Use segment ID to break ties.
4. Select up to N **additional** segments. No similarity floor is imposed in this profile. Record actual neighbor count and similarities.
5. For each selected segment and the query, form `r_i = normalize(mean(original_window_embeddings_i))`.
6. Form `q_comp = normalize(mean(r_query, r_neighbor_1, ..., r_neighbor_k))`. Give each segment equal weight, irrespective of duration or window count.
7. Score `Q_effective = [q_comp]` against the enrollment window sets using §6. Preserve the original query interval in the output.

If no eligible neighbor exists, use the original query matrix unchanged. If a mean becomes zero or non-finite, fall back to uncompensated scoring and record the reason. Always select neighbors from original embeddings, never previously compensated vectors; results must be independent of iteration order.

This is embedding-level compensation followed by score-level gallery pooling. It is not the same as averaging final identity scores over neighbors. The implementation must expose the profile name so later author code can replace this approximation without silently changing prior experiments.

## 8. Reference pseudocode

```text
validate_config_and_manifests()
encoder = load_encoder_with_provenance()
E = embed_each_enrollment_utterance_and_keep_windows()
C = build_or_load_cohort_centroids() if scoring == asnorm else None
enrollment_stats = cohort_stats(E, C) if C is not None else None

for session in sessions:
    G = select_declared_gallery(session, policy)
    original = embed_all_valid_selected_provider_segments(session)
    for segment in session.input_order:
        if segment has invalid audio or embeddings:
            emit_error_record(segment)
            continue
        if G is empty:
            emit_empty_gallery_record(segment)
            continue
        Q = original[segment.id]
        neighbors = []
        if compensation != none and segment.duration_s < 4.0:
            Q, neighbors = compensate_from_original_embeddings(segment, original)
        scores = {g: mean_pairwise_trial_score(E[g], Q, C) for g in G}
        emit_scored_or_thresholded_record(segment, scores, neighbors)
```

Configuration validation precedes model work. A missing cohort must not silently switch an AS-Norm run into a cosine run.

## 9. Configuration and reproducibility

Proposed configuration shape; null asset fields must be resolved before their corresponding operation is runnable:

```yaml
method: ecapa_asnorm
diarization_provider: deepgram-asr  # Or openrouter-mai-transcribe-2 for a separate run.
encoder:
  model_id: speechbrain/spkrec-ecapa-voxceleb
  revision: null  # Resolve and record an immutable revision before the run.
  checkpoint: null  # Download from the resolved revision and record its hash.
  adapter: speechbrain
  expected_embedding_dim: 192
  preprocessing_manifest: null
audio:
  sample_rate: 16000
  channel_policy: first
  window_s: 4.0
  shift_s: 1.5
  tail_policy: end_aligned_unique
  short_policy: native_length_then_minimum_zero_pad
  boundary_margin_s: 0.0
gallery:
  manifest: null
  policy: all_enrolled
  session_candidates_manifest: null
scoring:
  normalization: asnorm
  pooling: mean_all_window_pairs
  threshold: null
cohort:
  manifest: null
  corpus: VoxBlink2
  speaker_count: 2000
  representation: speaker_centroid_v1
  adaptive_k: 20
  std_ddof: 0
  std_floor: 0.000001
compensation:
  mode: none
  profile: short4_equal_segment_mean_v1
runtime:
  device: cpu
  seed: 0
```

Support explicit CPU or CUDA devices. GPU timings require synchronization around measured regions. Separate cold model loading, enrollment/cohort preparation, warm query embedding, compensation, scoring, and end-to-end mapping. Report cache hits and exclude cached extraction from fresh-extraction latency summaries.

Cache keys include audio content and interval, encoder and preprocessing hashes, window policy, cohort manifest, gallery, and compensation profile as applicable. Keep CAM++ and ECAPA caches physically separate. Store the resolved configuration and asset hashes with every run.

## 10. Later evaluation contract

Evaluation is deferred, but implementation must retain scores and provenance needed for it. Ground truth remains external to inference.

Prepare four principal comparisons on identical diarized query intervals and enrollment references:

| Method | Encoder | Score | Compensation |
| --- | --- | --- | --- |
| A | Existing CAM++ | Existing pairwise cosine; current threshold 0.6 | None |
| B | ECAPA | Raw cosine | None |
| C | ECAPA | AS-Norm | None |
| D | ECAPA | AS-Norm | Top-3 approximation above |

Also support top-1/top-2 runs. Compare A's current operating point separately from calibrated operating points. A chronological production replay that updates/creates voice nodes is a different experiment from a frozen enrollment comparison and must be labeled accordingly. Do not silently resolve that distinction through code reuse.

Use separate enrollment, calibration, and final-test audio; prevent duplicate or overlapping source intervals across splits. Compensation groups must not cross split boundaries. Include unseen identities, changed local labels across clips, weak/noisy speech, and short queries. Keep verified annotations distinct from model-generated identities.

For valid single-speaker labeled evaluation units, define:

```text
DIR(theta) = correctly identified and accepted known units / all known units
FAR(theta) = unknown units assigned any enrolled ID / all unknown units
FRR(theta) = known units rejected as non_target / all known units
wrong_known(theta) = known units assigned a different enrolled ID / all known units
rank1_accuracy = known units whose best candidate is correct / all known units
```

Report invalid/missed units separately and retain them in the known-unit denominator where the evaluation protocol requires coverage. Do not call unknown true-rejection accuracy “known identification accuracy.”

Project calibration rule: for each target FAR in `{0.005, 0.01, 0.05, 0.10}`, choose the most permissive calibration threshold whose empirical unknown FAR is no greater than the target, respecting ties and `>=` acceptance. Freeze it for the test split. Report test DIR and **achieved test FAR**; calibration at 1% does not guarantee test FAR equals 1%. Label any test-curve DIR@FAR separately as descriptive, not a deployable calibration result. Report sample counts and uncertainty when unknown coverage is sparse.

No measured improvement can be attributed solely to the encoder, AS-Norm, or compensation unless the corresponding comparison holds the remaining settings fixed.

## 11. Acceptance checks and fidelity limits

Required tests before a measured rerun:

- Hand-computed AS-Norm, top-k selection, population standard deviation, and finite handling at near-zero variance.
- Mean of window-pair trial scores differs from and is not replaced by centroid cosine.
- Window counts/timestamps at durations below 4 seconds, exactly 4 seconds, 5.5 seconds, and an irregular tail; no duplicate end window.
- Consistent embedding dimension and preprocessing across query, enrollment, and cohort.
- Same person may map to one global ID despite changing local labels; identical local labels across sessions never share compensation.
- Singleton and missing-label groups remain uncompensated; fewer than N neighbors work; self-selection and recursive compensation are impossible.
- Threshold equality accepts; valid low scores reject; invalid audio is distinguishable from non-target speech.
- Changing transcript text while keeping audio and diarization fixed cannot change identity scores.
- Candidate subsets constrain outputs; full-gallery mode is explicitly recorded; unknowns do not create nodes.
- No VLM/text-embedding/retrieval dependency or network call is required by mapping; production caches and graph state remain unchanged.

Describe the deliverable as a **paper-informed mapping algorithm using a standard pretrained ECAPA-TDNN**, not an exact checkpoint reproduction. Obtaining the paper's encoder is not a prerequisite. Cohort utterance selection and representation, window-edge policy, compensation arithmetic and application rule, and calibration conventions remain documented reproduction choices. The source's algorithm settings and the project's choices above must remain separately identifiable in code, configuration, and reports.
