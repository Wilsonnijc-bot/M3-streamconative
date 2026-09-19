# Latency

Nested stages overlap; values are measured independently. Missing values remain missing.

## Construction (current hour)

Stage | N | Mean ms | Median ms | P95 ms
--- | ---: | ---: | ---: | ---:
asr_total | 0 | — | — | —
audio_segmentation | 1 | 3.85 | 3.85 | 3.85
clip_decode | 1 | 1981.70 | 1981.70 | 1981.70
deepgram_asr | 0 | — | — | —
face_clustering | 1 | 3.22 | 3.22 | 3.22
facial_detection_recognition_buffalo_l | 1 | 1255.46 | 1255.46 | 1255.46
graph_update_total | 1 | 10.38 | 10.38 | 10.38
mai_transcribe_asr | 0 | — | — | —
speaker_mapping_including_embedding | 1 | 10.16 | 10.16 | 10.16
speech_embedding_campplus | 0 | — | — | —
speech_embedding_ecapa | 1 | 0.00 | 0.00 | 0.00
text_embedding | 1 | 459.62 | 459.62 | 459.62
vlm_memory_generation | 1 | 13349.54 | 13349.54 | 13349.54

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
  "input_nodes": 25,
  "consolidation_start": 1789756865.3169558,
  "snapshot_copy_ms": 34.99627400015015,
  "queue_ms": 0.23272499674931169,
  "snapshot_input_preparation_ms": 2.485902004991658,
  "llm_ms": 67039.9801809981,
  "usage": {
    "input_tokens": 6418,
    "input_tokens_details": {
      "cache_write_tokens": 2918,
      "cached_tokens": 3484
    },
    "output_tokens": 4200,
    "output_tokens_details": {
      "reasoning_tokens": 3106
    },
    "total_tokens": 10618
  },
  "reason_worker_ms": 77163.90590601077,
  "phase_timings": {
    "scope": "shared worker including evidence, MOSS, reasoning and projection",
    "worker_wall_ms": 77158.38492500188
  },
  "accepted_decisions": 4,
  "rejected_decisions": 3,
  "job_directory": "smoke/maintenance_terra01/C4/consolidation/snapshot_2",
  "write_back_ms": 0.5430059973150492,
  "affected_nodes": [
    17,
    18,
    19,
    20
  ],
  "reindex_ms": 663.6335079965647,
  "reindex_report": {
    "changed_node_ids": [
      17,
      18,
      19,
      20
    ],
    "embedded_text_count": 4,
    "backend": {
      "kind": "configured_m3",
      "alias": "text-embedding-3-large",
      "model": "text-embedding-3-large",
      "endpoint": "https://api.openai.com/v1",
      "provider": "openai"
    },
    "unchanged_text_node_ids": [
      4,
      5,
      6,
      7,
      8,
      9,
      10,
      11,
      12,
      13,
      14,
      15,
      16,
      21,
      22,
      23,
      24
    ]
  },
  "consolidation_end": 1789756943.1808777,
  "total_consolidation_wall_ms": 77863.92644800071,
  "construction_blocked_ms": 77864.15349299205,
  "llm_call_count": 1,
  "status": "accepted",
  "media_timestamp": 1200
}
```

```json
{
  "cutoff": 2400,
  "input_nodes": 25,
  "consolidation_start": 1789756943.223888,
  "snapshot_copy_ms": 39.25823399913497,
  "queue_ms": 0.38495099579449743,
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
  "affected_nodes": [],
  "consolidation_end": 1789756948.965761,
  "total_consolidation_wall_ms": 5741.884860006394,
  "construction_blocked_ms": 5742.23921399971,
  "llm_call_count": 1,
  "status": "accepted",
  "media_timestamp": 2400
}
```

```json
{
  "cutoff": 3600,
  "input_nodes": 25,
  "consolidation_start": 1789756949.0043712,
  "snapshot_copy_ms": 35.35364799608942,
  "queue_ms": 0.15636200259905308,
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
  "affected_nodes": [],
  "consolidation_end": 1789756955.1465907,
  "total_consolidation_wall_ms": 6142.2271150076995,
  "construction_blocked_ms": 6142.369320994476,
  "llm_call_count": 1,
  "status": "accepted",
  "media_timestamp": 3600
}
```

