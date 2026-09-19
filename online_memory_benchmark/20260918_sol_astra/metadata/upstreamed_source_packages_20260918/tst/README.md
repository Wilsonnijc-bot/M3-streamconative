# Offline TST speaker mapping

This is a paper-informed identity mapper using a standard pretrained ECAPA-TDNN,
not an exact reproduction of the paper's encoder. It does not invoke an ASR
service, CAM++, VideoGraph, text embeddings, or enrollment discovery. Prepare
segments from one selected diarization provider and verified enrollment audio
externally. Do not merge providers within a run. The score-only
mode needs no calibration threshold; mapping mode requires one calibrated on
separate audio. No benchmark result is implied.

From the repository root, install `pip install -r tst/requirements.txt`, then run:

```sh
python -m tst.runner --config tst-config.json --segments segments.jsonl \
  --enrollment enrollment.jsonl --cohort cohort.jsonl \
  --session-candidates sessions.json --output tst-results.jsonl
```

`--cohort` is required only for AS-Norm. `--session-candidates` is required
only for `session_subset`. Relative audio paths resolve relative to their own
manifest. `session_id` must identify one diarization invocation; never reuse
one across clips merely because their local speaker numbers match. Supply
`timestamp_precision: "rounded"` if only whole-second timestamps are available.

Queries shorter than 1 second receive `short_audio_flag: true` and are counted
separately in run metadata; a valid embedding is still scored. Durations from
1 through 4 seconds use the whole crop once; over 4 through 5.5 seconds use
start and end-aligned 4-second windows; longer crops use 4-second windows at
1.5-second shifts plus a unique end-aligned tail.

The configuration is JSON or YAML. A score-only cosine example:

```json
{
  "diarization_provider": "deepgram-asr",
  "encoder": {
    "model_id": "speechbrain/spkrec-ecapa-voxceleb",
    "revision": "REPLACE_WITH_40_CHARACTER_HUGGINGFACE_COMMIT",
    "expected_embedding_dim": 192,
    "minimum_samples": 0
  },
  "audio": {
    "sample_rate": 16000, "channel_policy": "first",
    "window_s": 4.0, "shift_s": 1.5, "tail_policy": "end_aligned_unique",
    "short_policy": "native_length_then_minimum_zero_pad", "boundary_margin_s": 0.0
  },
  "gallery": {"policy": "all_enrolled"},
  "scoring": {"normalization": "cosine", "threshold": null},
  "compensation": {"mode": "none", "profile": "short4_equal_segment_mean_v1"},
  "runtime": {"device": "cpu", "offline": false, "cache_dir": "tst_cache"}
}
```

Each segment JSONL row has `session_id`, `clip_id`, globally unique
`segment_id`, `audio_path`, `start_s`, `end_s`, `local_speaker_id` (possibly
null), `diarization_provenance` equal to the configured provider alias,
`timestamp_precision: "raw"` or
`"rounded"`, and optional `transcript`. An enrollment row has
`global_speaker_id`, `source_id`, `verification_provenance`, `audio_path`,
`start_s`, `end_s`. Multiple rows per enrolled speaker retain separate
utterance boundaries. A cohort row has `speaker_id`, `source_id`, `corpus`,
`sha256` (hash of the audio file), `audio_path`, `start_s`, `end_s`. For strict
AS-Norm, add `cohort` config with `corpus: "VoxBlink2"`, `seed` (selection
seed), `speaker_count: 2000`, `representation: "speaker_centroid_v1"`,
`adaptive_k: 20`, `std_ddof: 0`, and `std_floor: 0.000001`. Exactly 2,000
distinct supplied speakers are required. Smaller or alternate corpora require
`approximate: true` and a fresh threshold. Candidate subset JSON is a mapping
from every session ID to a list of enrolled global IDs, including `[]` for an
empty gallery.

Set `normalization` to `asnorm` and supply the cohort for AS-Norm. Set
compensation `mode` to `top1`, `top2`, or `top3` to use the documented offline
short-query approximation; the default is `none`. The `method_id` in the
score-only `.run.json` identifies the selected diarization provider, encoder,
scoring, cohort, gallery, and
compensation settings. After separate calibration, set a finite `threshold`
and supply `threshold_artifact` under `scoring`:

```json
{"method_id": "SCORE_ONLY_RUN_METHOD_ID", "threshold": 0.0,
 "calibration_data_id": "INDEPENDENT_CALIBRATION_SET_ID"}
```

Use the actual calibrated threshold in both fields. The runner checks the
artifact against the current method ID. Inference never consults truth labels.
The output JSONL contains every segment, including invalid-audio errors, and
`<output>.run.json` records configuration, manifest hashes, checkpoint and
preprocessing hashes, versions, timings, and cache counts. Cached extraction
has zero fresh embedding time. The model snapshot is the only network-capable
stage; use `offline: true` with an already available snapshot. Keep the TST
cache separate from any CAM++ cache.
