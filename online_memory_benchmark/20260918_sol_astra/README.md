# Online long-horizon memory benchmark — Sol / Astra

Status: full benchmark NOT launched. The retained remote tmux readiness session exited 2 on required input and implementation gates. No construction or QA inference ran.

Local folder: `online_memory_benchmark/20260918_sol_astra`.
Remote folder: `/opt/streammeco/run/online_memory_benchmark/20260918_sol_astra`.
Hyperstack instance: `1042997`, RTX A6000; current SSH endpoint `ubuntu@38.80.122.150`.
Tmux readiness session: `online-memory-sol-astra-20260918-readiness` (exited pane retained).

- `specification.md`: supplied benchmark specification, including C4.
- `source/`: reused code and older shell references at preparation time; this is not an integrated runnable benchmark.
- `configs/run_request.json`: pinned `gpt-5.6-sol` at medium reasoning for primary/final answers, and `gpt-6-astra` at high for consolidation. The official Sol model endpoint returned HTTP 200 both locally and on the VM. No fallback model is permitted.
- `configs/jake_questions.json`: the existing Jake DAY1 first-ten schedule, with original clock times converted to seconds since midnight; ten questions.
- `configs/aea_questions.json`: 1,994 original EgoEverything questions using the already derived causal AEA schedule. These are derived ask times, not timestamps in the original annotations.
- `scripts/build_question_manifests.py`: reproducible normalization from source QA/schedule.
- `scripts/launch_readiness.sh`: launches a fail-closed tmux diagnostic; it does not start benchmark inference. Remote key is held outside this folder in `/opt/streammeco/secrets/online_memory.env`, mode 600.
- `metadata/readiness.json`, `metadata/readiness_exit_status.txt`, `logs/readiness.log`: observed VM readiness outcome.
- `results/`: reserved for new benchmark results; no prior results reused.

The VM passes a CUDA arithmetic check, has all 109 AEA recording paths, both normalized question manifests, and official Sol model access. The benchmark is blocked by: (1) no integrated online C1–C4 event-clock runner, (2) no verified TST enrollment and independently calibrated threshold for Jake or AEA. The VM currently has 2.75 GiB free on its 97 GiB root disk; this is recorded as a capacity risk, not a launch gate. Peak space will be measured on a short prefix with bounded temporary media and hourly/shared query-time snapshots before the full run. The current offline TST runner and AEA stream runner do not meet the C1–C4 and paired retrieval requirements. No benchmark accuracy or latency metric exists.

Readiness on the GPU: `tmux attach -t online-memory-sol-astra-20260918-readiness`. The pane has exited with status 2; inspect `logs/readiness.log`. Do not respawn it as a full benchmark.

Storage inventory (read-only, 2026-09-18): pip download cache 2.2 GiB (~2.13 GiB unique-link), uv cache 8.1 GiB but only ~0.14 GiB unique-link due to hard links into installed environments, apt archive ~0.15 GiB. Five older generated `work/segments` directories total about 13.5 GiB unique-link. They are reconstructible media slices but retained as prior run provenance and possible resume inputs. No cleanup was performed. No fixed extra-space requirement is asserted before a measured run footprint; avoid retaining per-clip full graph pickles and temporary segment MP4s in the new implementation.
