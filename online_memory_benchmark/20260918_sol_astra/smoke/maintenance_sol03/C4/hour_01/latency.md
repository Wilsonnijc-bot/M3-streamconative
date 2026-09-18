# Latency

Nested stages overlap; values are measured independently. Missing values remain missing.

## Construction (current hour)

Stage | N | Mean ms | Median ms | P95 ms
--- | ---: | ---: | ---: | ---:
asr_total | 0 | — | — | —
audio_segmentation | 1 | 6.55 | 6.55 | 6.55
clip_decode | 1 | 2022.62 | 2022.62 | 2022.62
deepgram_asr | 0 | — | — | —
face_clustering | 1 | 2.78 | 2.78 | 2.78
facial_detection_recognition_buffalo_l | 1 | 1642.74 | 1642.74 | 1642.74
graph_update_total | 1 | 11.45 | 11.45 | 11.45
mai_transcribe_asr | 0 | — | — | —
speaker_mapping_including_embedding | 1 | 11.04 | 11.04 | 11.04
speech_embedding_campplus | 0 | — | — | —
speech_embedding_ecapa | 1 | 0.00 | 0.00 | 0.00
text_embedding | 1 | 587.76 | 587.76 | 587.76
vlm_memory_generation | 1 | 151266.19 | 151266.19 | 151266.19

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
  "input_nodes": 12,
  "consolidation_start": 1789752987.5369663,
  "snapshot_copy_ms": 13.308431996847503,
  "queue_ms": 0.23286401119548827,
  "snapshot_input_preparation_ms": 2.783261996228248,
  "llm_ms": 26731.92388100142,
  "usage": {
    "input_tokens": 5464,
    "input_tokens_details": {
      "cache_write_tokens": 1964,
      "cached_tokens": 3484
    },
    "output_tokens": 1461,
    "output_tokens_details": {
      "reasoning_tokens": 964
    },
    "total_tokens": 6925
  },
  "reason_worker_ms": 36575.32093199552,
  "phase_timings": {
    "scope": "shared worker including evidence, MOSS, reasoning and projection",
    "worker_wall_ms": 36572.42751499871
  },
  "accepted_decisions": 2,
  "rejected_decisions": 0,
  "job_directory": "smoke/maintenance_sol03/C4/consolidation/snapshot_2",
  "write_back_ms": 0.4187119920970872,
  "affected_nodes": [],
  "consolidation_end": 1789753024.1131554,
  "total_consolidation_wall_ms": 36576.194673994905,
  "construction_blocked_ms": 36576.42142700206,
  "llm_call_count": 1,
  "status": "accepted",
  "media_timestamp": 1200
}
```

```json
{
  "cutoff": 2400,
  "input_nodes": 12,
  "consolidation_start": 1789753024.1306415,
  "snapshot_copy_ms": 14.296909008407965,
  "queue_ms": 0.10565700358711183,
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
  "affected_nodes": [],
  "consolidation_end": 1789753030.022537,
  "total_consolidation_wall_ms": 5891.901323993807,
  "construction_blocked_ms": 5891.996239995933,
  "llm_call_count": 1,
  "status": "accepted",
  "media_timestamp": 2400
}
```

```json
{
  "cutoff": 3600,
  "input_nodes": 12,
  "consolidation_start": 1789753030.0403209,
  "snapshot_copy_ms": 14.412396005354822,
  "queue_ms": 0.09341500117443502,
  "snapshot_input_preparation_ms": 2.4751849996391684,
  "llm_ms": 5629.477391994442,
  "usage": {
    "input_tokens": 4502,
    "input_tokens_details": {
      "cache_write_tokens": 1002,
      "cached_tokens": 3484
    },
    "output_tokens": 91,
    "output_tokens_details": {
      "reasoning_tokens": 47
    },
    "total_tokens": 4593
  },
  "reason_worker_ms": 5662.698528001783,
  "phase_timings": {
    "scope": "shared worker including evidence, MOSS, reasoning and projection",
    "worker_wall_ms": 5659.880813997006
  },
  "accepted_decisions": 0,
  "rejected_decisions": 0,
  "job_directory": "smoke/maintenance_sol03/C4/consolidation/snapshot_6",
  "write_back_ms": 0.5908150051254779,
  "affected_nodes": [],
  "consolidation_end": 1789753035.7039945,
  "total_consolidation_wall_ms": 5663.679031000356,
  "construction_blocked_ms": 5663.763550008298,
  "llm_call_count": 1,
  "status": "accepted",
  "media_timestamp": 3600
}
```

