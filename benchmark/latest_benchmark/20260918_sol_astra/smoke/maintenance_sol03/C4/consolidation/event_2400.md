# Consolidation at 2400 media seconds

Detailed snapshot, evidence, official request/response, accepted/rejected decisions, and native identity changes are in snapshot job directories.

```json
{
  "cutoff": 2400,
  "input_nodes": 12,
  "consolidation_start": 1789753024.1306415,
  "snapshot_copy_ms": 14.296909008407965,
  "queue_ms": 0.10565700358711183,
  "before_mappings": {
    "character_0": [
      "voice_0",
      "voice_1",
      "voice_3"
    ],
    "character_2": [
      "voice_2"
    ]
  },
  "snapshot_input_preparation_ms": 2.237312000943348,
  "llm_ms": 5859.572935994947,
  "usage": {
    "input_tokens": 4502,
    "input_tokens_details": {
      "cache_write_tokens": 1002,
      "cached_tokens": 3484
    },
    "output_tokens": 97,
    "output_tokens_details": {
      "reasoning_tokens": 53
    },
    "total_tokens": 4599
  },
  "reason_worker_ms": 5890.837004000787,
  "phase_timings": {
    "scope": "shared worker including evidence, MOSS, reasoning and projection",
    "worker_wall_ms": 5887.950028991327
  },
  "accepted_decisions": 0,
  "rejected_decisions": 0,
  "job_directory": "smoke/maintenance_sol03/C4/consolidation/snapshot_4",
  "write_back_ms": 0.5377649940783158,
  "after_mappings": {
    "character_0": [
      "voice_0",
      "voice_1",
      "voice_3"
    ],
    "character_2": [
      "voice_2"
    ]
  },
  "affected_nodes": [],
  "consolidation_end": 1789753030.022537,
  "total_consolidation_wall_ms": 5891.901323993807,
  "construction_blocked_ms": 5891.996239995933,
  "llm_call_count": 1,
  "status": "accepted",
  "media_timestamp": 2400
}
```
