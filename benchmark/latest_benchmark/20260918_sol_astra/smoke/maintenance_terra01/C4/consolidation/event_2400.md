# Consolidation at 2400 media seconds

Detailed snapshot, evidence, official request/response, accepted/rejected decisions, and native identity changes are in snapshot job directories.

```json
{
  "cutoff": 2400,
  "input_nodes": 25,
  "consolidation_start": 1789756943.223888,
  "snapshot_copy_ms": 39.25823399913497,
  "queue_ms": 0.38495099579449743,
  "before_mappings": {
    "character_0": [],
    "character_2": [
      "voice_2"
    ],
    "character_3": [],
    "character_1": [
      "voice_1"
    ]
  },
  "snapshot_input_preparation_ms": 6.55564600310754,
  "llm_ms": 5669.95831199165,
  "usage": {
    "input_tokens": 4521,
    "input_tokens_details": {
      "cache_write_tokens": 1021,
      "cached_tokens": 3484
    },
    "output_tokens": 99,
    "output_tokens_details": {
      "reasoning_tokens": 55
    },
    "total_tokens": 4620
  },
  "reason_worker_ms": 5740.380785995512,
  "phase_timings": {
    "scope": "shared worker including evidence, MOSS, reasoning and projection",
    "worker_wall_ms": 5733.4486549953
  },
  "accepted_decisions": 0,
  "rejected_decisions": 0,
  "job_directory": "smoke/maintenance_terra01/C4/consolidation/snapshot_4",
  "write_back_ms": 0.8230800012825057,
  "after_mappings": {
    "character_0": [],
    "character_2": [
      "voice_2"
    ],
    "character_3": [],
    "character_1": [
      "voice_1"
    ]
  },
  "affected_nodes": [],
  "consolidation_end": 1789756948.965761,
  "total_consolidation_wall_ms": 5741.884860006394,
  "construction_blocked_ms": 5742.23921399971,
  "llm_call_count": 1,
  "status": "accepted",
  "media_timestamp": 2400
}
```
