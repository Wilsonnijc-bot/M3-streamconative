# Verified Full Benchmark Launch

Session: `online-memory-terra-sol-20260918-full-01` on Hyperstack instance `1042997`.
The full worker PID was `352850`, with 11,418 MiB GPU memory in use, a live tmux
pane, `LAUNCH_GATE_PASS`, and `EVENT_START jake`. No exit-status file existed.
This verifies launch and processing, not benchmark completion.

- Answers: official `gpt-5.6-terra`, medium reasoning.
- Consolidation: official `gpt-5.6-sol`, high reasoning.
- C1-C4, 102 Jake questions, 1,000 AEA questions, five-minute graph snapshots.
- Shared `consolidation.port.attach_online` and `consolidate_until` own maintenance.
  The benchmark supplies evidence and records returned results; it has no private
  runtime overrides. The old copied package is archived and replaced by a link.
- 17 remote benchmark tests passed without skips. Both GPU prefix smokes passed
  all 16 paired answer checks. Six real Sol maintenance events and native reindexing
  passed on real prefix graphs with explicitly synthetic missing-media clock gaps.
- The shared source fixes cover Sol JSON-mode input and MOSS missing-media tails;
  raw inference outputs and exact inferred cutoffs remain preserved.

Remote log:
`/opt/streammeco/run/online_memory_benchmark/20260918_sol_astra/logs/online-memory-terra-sol-20260918-full-01.log`

Results: `results/` under that same remote root. Status and exit receipt:
`metadata/online-memory-terra-sol-20260918-full-01.status` and `.exit_status`.

The original Jake recordings and reusable caches were preserved. The Mac can
sleep without stopping this detached remote tmux job.
