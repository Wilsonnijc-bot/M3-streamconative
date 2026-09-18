# AEA six-hour streaming-memory benchmark

This is an assembled stream of complete Project Aria AEA recordings, **not** an
original continuous six-hour recording. `aea_6h_manifest.json` lists the exact
order, within-session sequence chronology, session boundaries, measured MP4
durations, source Explorer pages, and cumulative stream offsets.

## Sources and selection

- `aea_download_urls.json`: official AEA URL manifest; only its
  `video_main_rgb` entries are fetched. URLs may expire; replace this input
  with a current authorized manifest when rebuilding.
- `Egoeverything_VQA.json`: original EgoEverything VQA annotations, obtained
  from the authors' `roxqtang/EgoEverything` release. Original question,
  options, answer, keyframes, and other fields are preserved in the schedule.
- Every available MP4 is probed with `ffprobe` for exact duration and an audio
  stream. The deterministic ordering favors `rec1` scripts 1, 4, 5, then
  scripts 2, 3; within each `(location, script, recording)` the `seq` numbers
  ascend. An entire session is included before switching sessions. `rec2`, if
  needed, is marked as an alternate wearer rather than consecutive activity.

The selected 109 MP4s total **21,788.950 seconds (6.052 hours)** and
**16,205,044,338 bytes (15.09 GiB)**. All selected MP4s have an audio stream.
The inspected first file has H.264 video and stereo 44.1 kHz MP3 audio; its
SHA-1 matches the official manifest. Each downloaded file is checksum-checked,
probed for both streams, and checked for A/V duration and start-time alignment.
No VRS, SLAM, IMU, eye tracking, point cloud, calibration, or MPS payload is
downloaded or retained. The M3 decode path resamples embedded audio to 16 kHz
PCM WAV in memory for ASR and speaker processing.

## Rebuild

From the repository root, with `ffprobe`, `ffmpeg`, and Python 3 available:

```bash
curl -fL -o aea_6h/Egoeverything_VQA.json \
  https://huggingface.co/datasets/roxqtang/EgoEverything/resolve/main/Egoeverything_VQA.json
python3 tools/build_aea_6h_manifest.py \
  --urls aea_6h/aea_download_urls.json --qa aea_6h/Egoeverything_VQA.json \
  --out aea_6h/aea_6h_manifest.json
python3 tools/build_aea_qa_schedule.py \
  --manifest aea_6h/aea_6h_manifest.json --qa aea_6h/Egoeverything_VQA.json \
  --out aea_6h/aea_6h_qa_schedule.json --seed 42
python3 tools/download_aea_6h.py \
  --urls aea_6h/aea_download_urls.json --manifest aea_6h/aea_6h_manifest.json \
  --destination /path/to/aea_6h --workers 8
```

When the media host is slow from the GPU network, download to local temporary
storage, then transfer verified files over SSH in parallel:

```bash
python3 tools/transfer_aea_6h.py \
  --urls aea_6h/aea_download_urls.json --manifest aea_6h/aea_6h_manifest.json \
  --source /path/to/local/aea_6h --host ubuntu@GPU_IP \
  --key /path/to/ssh_key --destination /opt/streammeco/aea_6h --workers 8
```

The transfer is rerunnable; incomplete local MP4s are skipped, and remote files
are checksum-verified before being exposed under their final names. Copy the
manifest and QA schedule into the remote dataset after regenerating them.

The download command fails closed if a selected MP4 lacks audio; this corpus
requires no VRS fallback. It checks free space with a 1 GiB reserve, writes
temporary `.part` files, verifies official byte length and SHA-1 before
renaming, and can be rerun after interruption. The final dataset contains
`videos/*.mp4`, `aea_6h_manifest.json`, and `aea_6h_qa_schedule.json` only.
The URL manifest and original VQA source file are build inputs, not retained
inside that final dataset.

## Questions and runner

`tools/build_aea_qa_schedule.py` assigns derived `ask_global_s` values at
20-minute checkpoints (fixed seed 42); original QA fields are not modified.
All scheduled questions satisfy `ask_global_s > evidence_global_s` and
`evidence_local_s <= duration_s`. Lag buckets and clip/session-crossing flags
are explicit. The two source questions whose evidence occurs after the last
360-minute checkpoint cannot be asked causally under this schedule.

The 1,994 scheduled questions have 995 recent, 574 medium, and 425 long
lags; 1,887 cross clip boundaries and 1,533 cross session boundaries. The
last checkpoint is heavy because 481 questions have evidence in the preceding
20 minutes; the schedule does not move those questions before their evidence.

The runner processes recordings in manifest order using one persistent
`VideoGraph`, cuts temporary RGB+audio segments at checkpoints, pauses to
retrieve and answer scheduled questions, and writes segment and answer JSONL
logs. It does not reset memory at session boundaries or include future media.
The full inference run can be expensive and is **not** part of the download:

```bash
python3 tools/run_aea_stream_benchmark.py \
  --dataset /opt/streammeco/aea_6h --results /opt/streammeco/run/aea_6h
```

It uses the repository's configured Gemini M3 reasoning path and credentials;
`--max-segments 1` supports a one-segment smoke test. Its full run has not
been executed or validated on this dataset yet.
