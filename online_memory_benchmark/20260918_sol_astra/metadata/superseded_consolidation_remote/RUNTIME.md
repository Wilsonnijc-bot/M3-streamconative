# Live construction and consolidation

The runtime is an opt-in wrapper around the existing M3 writer and consolidation
logic. It adds no identity namespace: native `character_mappings`, metadata,
observation assignments, and reference assignments remain authoritative. The
prompt, evidence policy, patch executor, and `native.project` are unchanged.

## Construction and snapshots

`ConsolidationRuntime` attaches to the live `VideoGraph`. The existing
`process_segment` entry point opens a writer segment when a runtime is attached;
the stream scheduler must supply the exact media end time as `sample['segment_end_s']`.
Other construction entry points use `with runtime.segment(clip_id, end_seconds)`.
There must be one ordered clip writer. Normal voice, face, episodic, semantic,
temporal, and embedding construction continues inside that call.

No runtime lock is held across clip processing or model calls. Individual graph
mutations and snapshot copies use a lock. Identity commits occur between clips,
so canonicalization cannot change halfway through a precomputed embedding batch.
Snapshot copying and in-memory commit work scale with graph size; this is not a
zero-latency or hard real-time guarantee. There is no network, model inference,
or file publication inside the live commit.

At a completed clip boundary, the default 1,200-second scheduler deep-copies the
native graph and records its construction revision, clip cutoff, and timestamp.
Nodes, edges, identity state, and embedding inputs in that snapshot cannot acquire
later observations. A worker that mutates its input snapshot is rejected.

## Worker, patch, and commit

`runtime_io.NativeConsolidationWorker` takes two adapters: the existing evidence
collector and the configured proposal callable. It passes frozen-prefix evidence
through the existing evidence builder, proposal call, executor, and native
application stage. It saves the snapshot, evidence, patch, execution report, and
identity report; existing proposal callables retain exact prompt/response files.

The returned patch contains the original snapshot and the staged native identity
result. Source-node or edge edits, cutoff violations, and mismatched identity bases
are rejected. The commit reconciles identity state against current native state;
it never replaces live nodes, embeddings, edges, or temporal indices with the old
snapshot. Concurrently allocated character IDs are retained and worker-local new
IDs are remapped monotonically when necessary.

Hot features assigned by construction to a subsequently merged character inherit
the surviving native character. Appending observations to a reviewed raw feature
invalidates global completeness; the existing strict >75% provisional admission
rule applies to those new observations. Mixed, unscoped features remain unresolved.

## Retrieval and background indexing

The live graph contains both hot and consolidated memory. Existing native retrieval
accepts that graph and captures a request-local read snapshot, including hot text
nodes. It ranks both regions using the same `search_text_nodes` path.

The commit records `current_graph_version`, `entity_registry_version`,
`last_consolidated_clip_id`, and `last_consolidated_timestamp`. Changed retrieval
representations receive `embedding_stale=True`. The worker uses the existing
canonicalizer and selective native reindexer; construction and retrieval do not
trigger synchronous catch-up embedding. During reindexing, old vectors remain
searchable, so ranking temporarily reflects their previous identity text.

Embedding results install only when the live identity revision, raw contents, and
effective canonical text still match. A superseded result is discarded and a new
pass is scheduled. No native audio, face, or image vectors are changed.

For automatic Mandol publication, supply `runtime_io.RetrievalPublisher`. It reuses
the existing dense/BM25/SPLADE builder and readiness checks and advances a separate
retrieval checkpoint pointer only after success. Use a dedicated runtime publication
directory. This checkpoint is never loaded over the growing live graph. Native M3
retrieval serves hot memory immediately; a persisted Mandol checkpoint contains only
the memory present in its indexed snapshot, not later hot arrivals.

## Wiring

```python
from functools import partial
from consolidation.runtime import ConsolidationRuntime
from consolidation.runtime_io import NativeConsolidationWorker, RetrievalPublisher
from consolidation.llm_consolidator import propose_official

# collect_evidence(snapshot) returns {replay, moss, assignments} using only the
# frozen prefix and its saved observation/audio evidence. Replay cutoff must match.
worker = NativeConsolidationWorker(
    collect_evidence,
    partial(propose_official, api_config=api_config_path),
    directory=run_directory / 'jobs',
)
runtime = ConsolidationRuntime(
    video_graph, worker,
    publish_index=RetrievalPublisher(run_directory / 'retrieval'),
)
# Existing process_segment calls now participate automatically when given
# sample['segment_end_s']. Legacy/custom clip writers use runtime.segment(...).
# On stream shutdown, after the final clip:
runtime.close()
```

No default API call is silently enabled. The deployment explicitly supplies its
existing evidence collector and configured proposal callable; tests use saved or
deterministic decisions. Runtime objects/locks/executors are excluded from pickles.
Native identity and watermarks persist; attach a new runtime after loading a checkpoint.

## Scheduling and failures

One sequential reasoning worker prevents conflicting historical jobs. While it is
busy, elapsed windows coalesce into the newest completed cutoff. A separate worker
handles indexing. Model or patch validation failure leaves identity and watermark
unchanged; streaming continues. `runtime.errors` records failures and
`runtime.retry()` retries the frozen failed window. Index failure retains old
vectors and the previous published index; retry explicitly or at the next completed
clip. No tight retry loop is used. `close()` waits for active jobs at shutdown only.

Deterministic tests cover clips 40–45 created/retrieved during a blocked clip-39
job, hot identity inheritance, immutable snapshots, cutoff rejection, atomic
failure/retry, selective/background reindexing, suffix completeness invalidation,
coalescing, writer-boundary commits, native application reuse, and publication rollback.
