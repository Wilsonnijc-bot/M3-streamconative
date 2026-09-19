# Consolidation at 3600 media seconds

Detailed snapshot, evidence, official request/response, accepted/rejected decisions, and native identity changes are in snapshot job directories.

```json
{
  "cutoff": 3600,
  "input_nodes": 12,
  "consolidation_start": 1789752981.2200842,
  "snapshot_copy_ms": 14.29118899977766,
  "queue_ms": 0.10507598926778883,
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
  "snapshot_input_preparation_ms": 2.5441540055908263,
  "llm_ms": 6255.4942160059,
  "usage": {
    "input_tokens": 4502,
    "input_tokens_details": {
      "cache_write_tokens": 1002,
      "cached_tokens": 3484
    },
    "output_tokens": 85,
    "output_tokens_details": {
      "reasoning_tokens": 41
    },
    "total_tokens": 4587
  },
  "reason_worker_ms": 6287.6226480002515,
  "phase_timings": {
    "scope": "shared worker including evidence, MOSS, reasoning and projection",
    "worker_wall_ms": 6284.963598998729
  },
  "accepted_decisions": 0,
  "rejected_decisions": 0,
  "job_directory": "smoke/maintenance_sol03/C3/consolidation/snapshot_6",
  "write_back_ms": 0.5603859899565578,
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
  "consolidation_end": 1789752987.50868,
  "total_consolidation_wall_ms": 6288.60044600151,
  "construction_blocked_ms": 6288.695043011103,
  "llm_call_count": 1,
  "status": "accepted",
  "media_timestamp": 3600
}
```
