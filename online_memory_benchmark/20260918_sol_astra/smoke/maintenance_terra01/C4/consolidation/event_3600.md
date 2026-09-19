# Consolidation at 3600 media seconds

Detailed snapshot, evidence, official request/response, accepted/rejected decisions, and native identity changes are in snapshot job directories.

```json
{
  "cutoff": 3600,
  "input_nodes": 25,
  "consolidation_start": 1789756949.0043712,
  "snapshot_copy_ms": 35.35364799608942,
  "queue_ms": 0.15636200259905308,
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
  "snapshot_input_preparation_ms": 2.900966996094212,
  "llm_ms": 5862.604815003579,
  "usage": {
    "input_tokens": 4521,
    "input_tokens_details": {
      "cache_write_tokens": 1021,
      "cached_tokens": 3484
    },
    "output_tokens": 103,
    "output_tokens_details": {
      "reasoning_tokens": 59
    },
    "total_tokens": 4624
  },
  "reason_worker_ms": 6140.78009800869,
  "phase_timings": {
    "scope": "shared worker including evidence, MOSS, reasoning and projection",
    "worker_wall_ms": 6133.9155940077035
  },
  "accepted_decisions": 0,
  "rejected_decisions": 0,
  "job_directory": "smoke/maintenance_terra01/C4/consolidation/snapshot_6",
  "write_back_ms": 0.8580860012443736,
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
  "consolidation_end": 1789756955.1465907,
  "total_consolidation_wall_ms": 6142.2271150076995,
  "construction_blocked_ms": 6142.369320994476,
  "llm_call_count": 1,
  "status": "accepted",
  "media_timestamp": 3600
}
```
