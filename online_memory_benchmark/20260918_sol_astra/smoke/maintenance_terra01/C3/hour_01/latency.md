# Latency

Nested stages overlap; values are measured independently. Missing values remain missing.

## Construction (current hour)

Stage | N | Mean ms | Median ms | P95 ms
--- | ---: | ---: | ---: | ---:
asr_total | 0 | — | — | —
audio_segmentation | 1 | 3.41 | 3.41 | 3.41
clip_decode | 1 | 1981.70 | 1981.70 | 1981.70
deepgram_asr | 0 | — | — | —
face_clustering | 1 | 3.04 | 3.04 | 3.04
facial_detection_recognition_buffalo_l | 1 | 1247.82 | 1247.82 | 1247.82
graph_update_total | 1 | 9.29 | 9.29 | 9.29
mai_transcribe_asr | 0 | — | — | —
speaker_mapping_including_embedding | 1 | 9.10 | 9.10 | 9.10
speech_embedding_campplus | 0 | — | — | —
speech_embedding_ecapa | 1 | 0.00 | 0.00 | 0.00
text_embedding | 1 | 569.22 | 569.22 | 569.22
vlm_memory_generation | 1 | 14771.39 | 14771.39 | 14771.39

## Mandol adapter/index construction (one sample per snapshot; excluded from warm retrieval)

Stage | N | Mean ms | Median ms | P95 ms
--- | ---: | ---: | ---: | ---:
M3 export | 0 | — | — | —
Adapter and index build total | 0 | — | — | —
Dense embedding (nested in build) | 0 | — | — | —
Index reload / warmup | 0 | — | — | —

Build totals include nested encoding/index stages; they are not added to question retrieval latency.

## R1 retrieval and answer (current hour)

Stage | N | Mean ms | Median ms | P95 ms
--- | ---: | ---: | ---: | ---:
retrieval | 0 | — | — | —
TTFT | 0 | — | — | —
full response | 0 | — | — | —
after first token | 0 | — | — | —
question to first token | 0 | — | — | —
question to completion | 0 | — | — | —

## R2 retrieval and answer (current hour)

Stage | N | Mean ms | Median ms | P95 ms
--- | ---: | ---: | ---: | ---:
retrieval | 0 | — | — | —
TTFT | 0 | — | — | —
full response | 0 | — | — | —
after first token | 0 | — | — | —
question to first token | 0 | — | — | —
question to completion | 0 | — | — | —

## Consolidation (current hour)

```json
{
  "cutoff": 1200,
  "input_nodes": 23,
  "consolidation_start": 1789756810.549969,
  "snapshot_copy_ms": 33.074022008804604,
  "queue_ms": 3.077910005231388,
  "snapshot_input_preparation_ms": 3.5759020101977512,
  "llm_ms": 32437.26361700101,
  "usage": {
    "input_tokens": 6392,
    "input_tokens_details": {
      "cache_write_tokens": 6376,
      "cached_tokens": 0
    },
    "output_tokens": 2054,
    "output_tokens_details": {
      "reasoning_tokens": 1552
    },
    "total_tokens": 8446
  },
  "reason_worker_ms": 42975.68406899518,
  "phase_timings": {
    "scope": "shared worker including evidence, MOSS, reasoning and projection",
    "worker_wall_ms": 42970.04566800024
  },
  "accepted_decisions": 2,
  "rejected_decisions": 0,
  "job_directory": "smoke/maintenance_terra01/C3/consolidation/snapshot_2",
  "write_back_ms": 0.44534400512930006,
  "affected_nodes": [],
  "consolidation_end": 1789756853.526568,
  "total_consolidation_wall_ms": 42976.60473099677,
  "construction_blocked_ms": 42979.672121000476,
  "llm_call_count": 1,
  "status": "accepted",
  "media_timestamp": 1200
}
```

```json
{
  "cutoff": 2400,
  "input_nodes": 23,
  "consolidation_start": 1789756853.56441,
  "snapshot_copy_ms": 34.84203800326213,
  "queue_ms": 0.12306999997235835,
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
  "affected_nodes": [],
  "consolidation_end": 1789756859.5486693,
  "total_consolidation_wall_ms": 5984.264821992838,
  "construction_blocked_ms": 5984.37331499008,
  "llm_call_count": 1,
  "status": "accepted",
  "media_timestamp": 2400
}
```

```json
{
  "cutoff": 3600,
  "input_nodes": 23,
  "consolidation_start": 1789756859.58424,
  "snapshot_copy_ms": 32.575566990999505,
  "queue_ms": 0.10203100100625306,
  "snapshot_input_preparation_ms": 2.3950320028234273,
  "llm_ms": 5621.203032991616,
  "usage": {
    "input_tokens": 4502,
    "input_tokens_details": {
      "cache_write_tokens": 1002,
      "cached_tokens": 3484
    },
    "output_tokens": 90,
    "output_tokens_details": {
      "reasoning_tokens": 46
    },
    "total_tokens": 4592
  },
  "reason_worker_ms": 5676.653118993272,
  "phase_timings": {
    "scope": "shared worker including evidence, MOSS, reasoning and projection",
    "worker_wall_ms": 5671.422611994785
  },
  "accepted_decisions": 0,
  "rejected_decisions": 0,
  "job_directory": "smoke/maintenance_terra01/C3/consolidation/snapshot_6",
  "write_back_ms": 0.6563779897987843,
  "affected_nodes": [],
  "consolidation_end": 1789756865.262044,
  "total_consolidation_wall_ms": 5677.8093530010665,
  "construction_blocked_ms": 5677.901577000739,
  "llm_call_count": 1,
  "status": "accepted",
  "media_timestamp": 3600
}
```

