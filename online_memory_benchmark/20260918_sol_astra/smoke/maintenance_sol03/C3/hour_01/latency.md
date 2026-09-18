# Latency

Nested stages overlap; values are measured independently. Missing values remain missing.

## Construction (current hour)

Stage | N | Mean ms | Median ms | P95 ms
--- | ---: | ---: | ---: | ---:
asr_total | 0 | — | — | —
audio_segmentation | 1 | 5.95 | 5.95 | 5.95
clip_decode | 1 | 2022.62 | 2022.62 | 2022.62
deepgram_asr | 0 | — | — | —
face_clustering | 1 | 2.63 | 2.63 | 2.63
facial_detection_recognition_buffalo_l | 1 | 1466.73 | 1466.73 | 1466.73
graph_update_total | 1 | 12.21 | 12.21 | 12.21
mai_transcribe_asr | 0 | — | — | —
speaker_mapping_including_embedding | 1 | 11.95 | 11.95 | 11.95
speech_embedding_campplus | 0 | — | — | —
speech_embedding_ecapa | 1 | 0.00 | 0.00 | 0.00
text_embedding | 1 | 583.47 | 583.47 | 583.47
vlm_memory_generation | 1 | 155715.99 | 155715.99 | 155715.99

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
  "consolidation_start": 1789752933.0197487,
  "snapshot_copy_ms": 12.753734990837984,
  "queue_ms": 0.6299669912550598,
  "snapshot_input_preparation_ms": 3.560052005923353,
  "llm_ms": 32116.488808998838,
  "usage": {
    "input_tokens": 5464,
    "input_tokens_details": {
      "cache_write_tokens": 5448,
      "cached_tokens": 0
    },
    "output_tokens": 1786,
    "output_tokens_details": {
      "reasoning_tokens": 1315
    },
    "total_tokens": 7250
  },
  "reason_worker_ms": 41932.9731780017,
  "phase_timings": {
    "scope": "shared worker including evidence, MOSS, reasoning and projection",
    "worker_wall_ms": 41929.598311005975
  },
  "accepted_decisions": 2,
  "rejected_decisions": 0,
  "job_directory": "smoke/maintenance_sol03/C3/consolidation/snapshot_2",
  "write_back_ms": 0.4226589953759685,
  "affected_nodes": [],
  "consolidation_end": 1789752974.9536226,
  "total_consolidation_wall_ms": 41933.884271013085,
  "construction_blocked_ms": 41934.50483100605,
  "llm_call_count": 1,
  "status": "accepted",
  "media_timestamp": 1200
}
```

```json
{
  "cutoff": 2400,
  "input_nodes": 12,
  "consolidation_start": 1789752974.9711566,
  "snapshot_copy_ms": 14.321505994303152,
  "queue_ms": 0.1026719983201474,
  "snapshot_input_preparation_ms": 2.23585800267756,
  "llm_ms": 6198.527428001398,
  "usage": {
    "input_tokens": 4502,
    "input_tokens_details": {
      "cache_write_tokens": 1002,
      "cached_tokens": 3484
    },
    "output_tokens": 96,
    "output_tokens_details": {
      "reasoning_tokens": 52
    },
    "total_tokens": 4598
  },
  "reason_worker_ms": 6230.642437003553,
  "phase_timings": {
    "scope": "shared worker including evidence, MOSS, reasoning and projection",
    "worker_wall_ms": 6227.823838999029
  },
  "accepted_decisions": 0,
  "rejected_decisions": 0,
  "job_directory": "smoke/maintenance_sol03/C3/consolidation/snapshot_4",
  "write_back_ms": 0.5561690049944445,
  "affected_nodes": [],
  "consolidation_end": 1789752981.2027833,
  "total_consolidation_wall_ms": 6231.631626011222,
  "construction_blocked_ms": 6231.726052006707,
  "llm_call_count": 1,
  "status": "accepted",
  "media_timestamp": 2400
}
```

```json
{
  "cutoff": 3600,
  "input_nodes": 12,
  "consolidation_start": 1789752981.2200842,
  "snapshot_copy_ms": 14.29118899977766,
  "queue_ms": 0.10507598926778883,
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
  "affected_nodes": [],
  "consolidation_end": 1789752987.50868,
  "total_consolidation_wall_ms": 6288.60044600151,
  "construction_blocked_ms": 6288.695043011103,
  "llm_call_count": 1,
  "status": "accepted",
  "media_timestamp": 3600
}
```

