# M3-Bench — bedroom_01

A separate experiment from the EgoLife Gemini and Qwen runs. Source: [ByteDance-Seed/M3-Bench bedroom_01](https://huggingface.co/datasets/ByteDance-Seed/M3-Bench/blob/main/videos/robot/bedroom_01.mp4).

- [Gemini run: progress and results](results/gemini/README.md)
- [Result and measurement contract](RESULT_CONTRACT.md)
- [Questions and reference answers](questions.md)

The 36:03.264 video is replayed chronologically from 73 source clips into 76 processing segments. The 15 questions use [timestamp-limited snapshots](QUERY_SCHEDULE.md), producing 60 answers across A/B/C/D. Reasoning uses `gemini-3.8-flash` via 302.ai. Existing EgoLife results remain under `egolife_m3_jake_day1/`.

Scripts are in `scripts/`; typed caches are in `cache/`; exact output, logs and checkpoints are in `provenance/`. This run has a separate remote directory and tmux session, `m3bench_bedroom_gemini`.

Refresh local results with `python3 scripts/sync_run.py` from this folder.
