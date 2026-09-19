# Consolidation at 2400 media seconds

Detailed snapshot, evidence, official request/response, accepted/rejected decisions, and native identity changes are in snapshot job directories.

```json
{
  "cutoff": 2400,
  "input_nodes": 23,
  "consolidation_start": 1789756853.56441,
  "snapshot_copy_ms": 34.84203800326213,
  "queue_ms": 0.12306999997235835,
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
  "snapshot_input_preparation_ms": 2.3679120058659464,
  "llm_ms": 5928.182420000667,
  "usage": {
    "input_tokens": 4502,
    "input_tokens_details": {
      "cache_write_tokens": 1002,
      "cached_tokens": 3484
    },
    "output_tokens": 93,
    "output_tokens_details": {
      "reasoning_tokens": 49
    },
    "total_tokens": 4595
  },
  "reason_worker_ms": 5983.109070002683,
  "phase_timings": {
    "scope": "shared worker including evidence, MOSS, reasoning and projection",
    "worker_wall_ms": 5977.649925000151
  },
  "accepted_decisions": 0,
  "rejected_decisions": 0,
  "job_directory": "smoke/maintenance_terra01/C3/consolidation/snapshot_4",
  "write_back_ms": 0.6243480020202696,
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
  "consolidation_end": 1789756859.5486693,
  "total_consolidation_wall_ms": 5984.264821992838,
  "construction_blocked_ms": 5984.37331499008,
  "llm_call_count": 1,
  "status": "accepted",
  "media_timestamp": 2400
}
```
