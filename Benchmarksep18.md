# Implement the online long-horizon memory benchmark

Use the existing benchmark runs as implementation references and **reuse their code paths, configs, logging, latency instrumentation, graph serialization, retrieval implementations, and output style wherever possible**.

try reuse: 
egolife_m3_jake_day1
```

Do not redesign working components unnecessarily.

## 1. Benchmark data

Run the benchmark independently on the two long-form datasets already present on the GPU:

* **EgoLife / Jake:** approximately 5+ hours.
* **AEA:** approximately 6 hours.

Locate the existing videos, QA annotations, timestamps, answers, and existing benchmark manifests from the supplied paths/repository.

Do **not** invent questions or timestamps.

Create a normalized question manifest:

```text
dataset
question_id
question
ground_truth
query_timestamp
source_annotation
```

The essential requirement is **online temporal evaluation**.

Questions must be asked at their actual benchmark timestamp during memory construction, rather than constructing the entire memory first and answering all questions afterward.

At query time `t`:

```text
memory may contain observations <= t
memory must contain no observations > t
```

If a processing clip crosses `t`, prevent future information from entering the query state. Split/limit the clip or use the last fully valid committed state.

This benchmark is driven by **video/event time**, not by how quickly the machine happens to process the video.

---

# 2. Construction ablations

Maintain **three completely independent memory graphs per dataset**.

## C1 — CAM++ baseline

```text
M3 Agent
+ native M3 CAM++ speaker mapping
+ StreamMeCo
```

StreamMeCo policy:

```text
retain_ratio = 0.50
compression_interval = 1 hour
```

Run compression at every completed hour.

---

## C2 — TST identity mapping

```text
M3 Agent
+ TST speaker mapping
+ StreamMeCo
```

Same StreamMeCo policy:

```text
retain_ratio = 0.50
compression_interval = 1 hour
```

Everything except speaker mapping should remain identical to C1.

---

## C3 — TST + consolidation

```text
M3 Agent
+ TST speaker mapping
+ online memory consolidation
+ StreamMeCo
```

Consolidation:

```text
interval = 20 minutes
```

Therefore consolidation events occur at:

```text
00:20
00:40
01:00
01:20
01:40
02:00
...
```

StreamMeCo remains:

```text
retain_ratio = 0.50
compression_interval = 1 hour
```

Do not merge these three construction runs. They must remain isolated graphs/checkpoints.

## C4 — TST + consolidation+70 stream

```
M3 Agent
+ TST speaker mapping
+ online memory consolidation
+ StreamMeCo
```

Consolidation:

```
interval = 20 minutes
```

Therefore consolidation events occur at:

```
00:20
00:40
01:00
01:20
01:40
02:00
...
```

StreamMeCo remains:

```
retain_ratio = 0.70
compression_interval = 1 hour
```

Do not merge these three construction runs. They must remain isolated graphs/checkpoints.

---

# 3. Deterministic event ordering

Use one deterministic benchmark/event clock.

For a normal media event:

```text
process observation
→ commit graph update
→ advance benchmark timestamp
```

At a scheduled 20-minute boundary for C3:

```text
finish all observations through timestamp t
→ run consolidation
→ atomically apply consolidation result
```

At an hourly boundary:

```text
finish observations through t
→ run scheduled consolidation if applicable
→ run StreamMeCo retain-50% compression
→ persist hourly graph snapshot
```

If a QA query has exactly the same timestamp as a maintenance boundary, use the **post-maintenance graph state** and record this explicitly.

Never allow maintenance or retrieval to introduce information from future video timestamps.

---

# 4. Online QA execution

For every question, when construction reaches its `query_timestamp`:

1. Finish graph commits valid through that timestamp.
2. Freeze an immutable query-time snapshot.
3. Run both retrieval methods against that exact same snapshot.
4. Record both results.
5. Resume memory construction.

This is important: retrieval latency must **not** cause one method to see a later graph than another.

Retrieval must be read-only and must not modify the underlying construction graph.

---

# 5. Retrieval ablation

Every construction graph is evaluated with **two retrieval systems**.

Therefore:

```text
C1 × R1
C1 × R2

C2 × R1
C2 × R2

C3 × R1
C3 × R2
also C4
```

## R1 — updated M3 retrieval

Use the current updated M3 retrieval implementation.

Requirements:

* exactly **one retrieval**
* no controller loop
* no iterative reasoning/retrieval
* exactly **one final answer LLM call**

Use the current canonicalization / identity-aware retrieval behavior already implemented.

---

## R2 — Mandol retrieval

Use the existing M3 → Mandol adaptor and Mandol retrieval implementation.

Requirements:

* exactly **one retrieval**
* no controller
* no second retrieval
* exactly **one final answer LLM call**

Reuse the currently implemented Mandol pipeline, including its existing hybrid retrieval/reranking configuration.

Do not reconstruct a different memory graph for Mandol. It must retrieve from the same query-time M3 state through the adaptor.

---

# 6. Keep QA conditions controlled

Across R1 and R2 keep identical wherever applicable:

* question text
* query timestamp
* frozen graph state
* final answer model
* answer prompt
* decoding parameters
* correctness evaluator
* ground truth

The retrieval method should be the main changed variable.

Record model names/configs in the run metadata.

---

# 7. Hourly memory replay

Persist graph checkpoints/replays at:

```text
1 hour
2 hours
3 hours
4 hours
5 hours
```

for each construction method.

For each hourly state create:

```text
memory.md
```

`memory.md` should make the graph state inspectable, not merely report a node count.

Include:

```text
dataset / method / benchmark timestamp

graph statistics
- total nodes
- episodic nodes
- semantic nodes
- voice nodes
- face nodes
- character/entity count
- edge count if applicable

character/entity mappings

memory replay grouped chronologically by clip/time
- timestamp
- episodic memory
- semantic memory
- speaker / identity association
- relevant face/voice nodes

StreamMeCo state
- nodes before compression
- nodes retained
- nodes removed
- actual retention ratio

changes since previous hourly snapshot
```

Also retain the machine-readable graph checkpoint needed to reproduce retrieval.

---

# 8. Consolidation replay

C3 performs consolidation every 20 minutes for the entire benchmark.

However, generate the **detailed human-readable consolidation replay only for the first hour**.

Capture the events at:

```text
00:20
00:40
01:00
```

The 1-hour consolidation replay should show, for each event:

```text
input graph/snapshot
entities/characters considered
relevant observations/transcripts
LLM consolidation request/result
identity merges or reassignment decisions
canonical-name changes
graph mutations
nodes/embeddings reindexed
before → after mappings
```

Preserve enough information to understand exactly why the graph changed.

Do not dump unrelated huge raw payloads into the Markdown; link/reference the raw audit artifact when appropriate.

---

# 9. Latency measurement

Reuse the existing detailed latency instrumentation.

Preserve the current construction measurements such as:

```text
clip decoding
ASR
audio segmentation
speaker embedding / speaker mapping
face detection
face clustering
VLM/context preparation
memory-generation LLM
memory-text embedding
graph update
queue/wait spans where applicable
admission → committed checkpoint
```

Preserve the existing retrieval breakdown for M3 and Mandol.

For example, where applicable:

```text
query preparation
query text embedding
dense/vector search
StreamMeCo/TMR scoring
graph selection
BM25
SPLADE/sparse retrieval
fusion
MemoryUnit / MemorySpace lookup
reranking
total retrieval wall time
```

Continue distinguishing nested/overlapping stages from sequential stages. Do not calculate total latency by blindly adding overlapping measurements.

---

# 10. NEW: consolidation latency

Add detailed timing for every consolidation event.

At minimum record:

```text
consolidation_start
consolidation_end
total_consolidation_wall_ms

snapshot/input preparation
LLM request
LLM time
result parsing
identity/entity resolution
graph mutation/write-back
embedding regeneration
index/reindex update

construction blocked time, if any
queue/wait time, if any
```

Also record:

```text
input nodes
affected nodes
merged identities
rewritten memories
reembedded nodes
LLM input tokens
LLM output tokens
LLM call count
```

If consolidation overlaps normal construction, explicitly record both:

```text
consolidation wall time
construction stall/block time
```

Do not assume they are equal.

---

# 11. NEW: LLM time-to-first-token

The current benchmark measures roughly:

```text
request/input → complete answer
```

Keep this metric, but add **TTFT: time to first generated content token**.

For every final-answer LLM request record:

```text
request_start_ts
first_content_token_ts
response_end_ts

ttft_ms =
    first_content_token_ts - request_start_ts

generation_complete_ms =
    response_end_ts - request_start_ts

after_first_token_ms =
    response_end_ts - first_content_token_ts
```

Use the provider's streaming response so the first token can actually be measured.

"First token" means the **first assistant content token/chunk received from the provider**, not HTTP headers, connection establishment, metadata, reasoning-status events, or an empty stream event.

Also record:

```text
input_tokens
output_tokens
model
provider
```

If the provider exposes reasoning tokens separately, keep them separately but do not redefine TTFT.

---

# 12. Retrieval latency boundary

Measure retrieval independently from answer generation.

Conceptually:

```text
question arrives
    ↓
retrieval starts
    ↓
evidence returned
    ↓
final LLM request starts
    ↓
first answer token
    ↓
complete answer
```

Record:

```text
retrieval_ms

LLM_ttft_ms
LLM_full_response_ms

question_to_first_token_ms
question_to_complete_answer_ms
```

Where:

```text
question_to_first_token
=
retrieval + answer-request overhead + LLM TTFT
```

Measure this directly from timestamps rather than deriving it only by adding averages.

Warm retrieval should continue excluding unrelated model/index initialization and benchmark warmup, consistent with the existing benchmark.

---

# 13. Output structure

Keep the output simple and consistent.

Suggested structure:

```text
benchmark/
  jake/
    C1_campp/
    C2_tst/
    C3_tst_consolidation/

  aea/
    C1_campp/
    C2_tst/
    C3_tst_consolidation/
```

Inside each construction run:

```text
hour_01/
  memory.md
  latency.md
  retrieval.md

hour_02/
  memory.md
  latency.md
  retrieval.md

...

hour_05/
  memory.md
  latency.md
  retrieval.md
```

For C3, the first-hour output should additionally contain/reference the detailed consolidation replay.

---

# 14. `latency.md`

Make this comparable to the existing latency reports.

For each hour report:

## Construction

Per-stage:

```text
N
mean
median
p95
```

plus relevant per-clip measurements.

## Consolidation

For C3:

```text
event timestamp
total wall time
LLM time
write-back time
reindex time
construction blocking time
input/output tokens
affected nodes
```

## Retrieval

Separate R1 and R2:

```text
mean retrieval
median retrieval
p95 retrieval

query embedding
local vector search
sparse/BM25
fusion
lookup
reranking
etc.
```

## Answer latency

For each retrieval method:

```text
mean/median/p95 TTFT
mean/median/p95 full LLM response
mean/median/p95 question → first token
mean/median/p95 question → complete answer
```

Never replace missing observations with zero.

---

# 15. `retrieval.md`

For every question that has occurred by that hour, record separately for R1 and R2:

```text
question ID
query timestamp
question
ground truth

graph checkpoint used
retrieval method

retrieved evidence
node IDs
node types
clip/timestamps
retrieval scores/ranks

final evidence supplied to LLM
final answer
correct / incorrect

retrieval latency
TTFT
full-answer latency
question → first-token latency
question → final-answer latency

input/output tokens
```

The document should make it possible to inspect **why** an answer succeeded or failed, not just its accuracy.

At the top include an aggregate table for the hour:

```text
Construction | Retrieval | Correct/N | Retrieval median | TTFT median | End-to-end median
```

Do not make retrieval accuracy judgments based on future questions that have not yet occurred.

---

# 16. Raw provenance

Markdown is the human-readable report, but preserve raw structured measurements as JSON/JSONL.

Every reported number must be traceable to raw events.

Record at least:

```text
dataset
construction_method
retrieval_method
benchmark_timestamp
wall_clock_timestamp
question_id / clip_id / consolidation_id
stage
start
end
duration
status
model/provider
```

Maintain separate benchmark/event time and wall-clock time.

---

# 17. Correctness requirements

Before the full run, validate with a short prefix that:

1. C1/C2/C3 are truly independent graphs.
2. TST actually replaces CAM++ mapping only where intended.
3. C3 consolidation executes every 20 benchmark minutes.
4. StreamMeCo executes every 60 benchmark minutes with `retain_ratio=0.50`.
5. Questions fire at their intended timestamps.
6. No query can retrieve memory from a future timestamp.
7. R1 and R2 receive the exact same frozen query-time graph state.
8. Both retrieval paths use exactly one retrieval and one final LLM call.
9. TTFT is measured from a streamed response.
10. Existing latency metrics remain compatible with the previous benchmark reports.

Then run the complete Jake and AEA benchmarks.

Do not simplify existing instrumentation. Reuse the previous benchmark architecture and make only the changes required for this online benchmark, TST/consolidation ablations, hourly snapshots, and the new latency metrics.
