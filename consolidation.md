# Offline Entity Memory Consolidation — Implementation Specification

## 1. Goal

Implement an **offline memory consolidation process** on top of the existing M3 memory graph.

The current graph creates many fragmented `voice_x` nodes across clips. The consolidator should periodically review accumulated evidence and create a more persistent canonical entity representation:

```text
voice_311 ─┐
voice_732 ─┼──> person_3
voice_... ─┘
             name: Katrina   # only when supported
```

```text
existing graph + acoustic evidence from MOSS + semantic memory
                    ↓
             strong LLM
                    ↓
          structured patch JSON
                    ↓
          deterministic executor
                    ↓
           updated graph/state
```

The first implementation should focus primarily on **voice → persistent person identity**.

Face consolidation can be added later.

---

# 2. Consolidation Schedule

Run consolidation approximately every **20 minutes of committed video memory**, plus once at the end of the video.

Example:

```text
0–20 min   → consolidation_1
0–40 min   → consolidation_2
0–60 min   → consolidation_3
final      → final consolidation
```

Use the actual latest committed M3 segment rather than cutting an in-progress segment.

Each run must record:

```json
{
  "session_id": "...",
  "base_graph_version": "...",
  "previous_cutoff": 1200.0,
  "current_cutoff": 2400.0
}
```

Different videos/datasets must have completely separate identity namespaces.

Never assume:

```text
video_A/voice_0 == video_B/voice_0
```

---

# 3. Immutable Speech Observation Ledger

Do not treat `voice_x` itself as the atomic unit of truth.

Create an immutable speech-observation layer.

Each speech segment should have:

```json
{
  "utterance_id": "utt_000123",
  "session_id": "egolife_day1",
  "clip_id": 65,

  "start_time": 1872.42,
  "end_time": 1876.81,

  "original_voice_id": "voice_732",

  "transcripts": {
    "Deepgram": "..."
  },

  "audio_ref": "...",

  "assignment_run_id": "...",
  "created_graph_version": "..."
}
```

Never overwrite:

```text
original_voice_id
original transcript
original assignment evidence
```

Consolidation creates a separate current interpretation:

```text
utterance_id → canonical person
```

This makes later correction possible.

---

# 4. Preserve Full Online Assignment Evidence

Extend the existing CAM++ / TST logging.

For every incoming speech observation, log the state **before graph mutation**.

Example:

```text
utterance: utt_123
transcript_source: MAI
transcript: 好，然后一个秒表。

CAM++ candidates:
voice_0: 0.74
voice_1: 0.42
voice_2: 0.38

threshold: 0.60

decision:
matched voice_0
```

If no candidate passes:

```text
decision:
new voice_7
best_existing:
voice_3 = 0.51
threshold = 0.60
```

For the first voice:

```text
new voice_0
reason: no existing voices
```

### Requirements

Store:

* every candidate that existed at that moment;
* full-precision similarity score;
* threshold;
* eligibility/rejection status;
* selected candidate;
* graph version before assignment;
* embedding/model version.

Do not recompute this historical display later.

---

# 5. TST Logging

Apply the same principle to TST.

For each speech segment show, for example:

```text
Katrina / enrollment_katrina: 0.74
Alice / enrollment_alice:    0.42
Shure / enrollment_shure:    0.31
non_target

chosen:
Katrina
```

Important:

* TST candidates correspond to **enrolled identities**, not arbitrary `voice_x` nodes.
* Keep `non_target` as rejection, not as one shared identity.
* Keep the TST enrollment gallery fixed for the initial evaluation.
* Do not mix TST scores numerically with CAM++ scores.
* Log model/version/configuration for each score.

If transcript-based TST compensation/grouping exists, preserve its intermediate result as evidence too.

---

# 6. MOSS Long-Context Diarization

At each consolidation point run:

```text
MOSS-Transcribe-Diarize 0.9B
```

over the available audio prefix.

Initial implementation:

```text
20 min consolidation → audio [0, 20 min]
40 min consolidation → audio [0, 40 min]
60 min consolidation → audio [0, 60 min]
```

This is intentionally redundant because the first goal is quality, not compute efficiency.

Namespace every MOSS run:

```text
moss_20/SPEAKER_00
moss_20/SPEAKER_01

moss_40/SPEAKER_00
moss_40/SPEAKER_01
```

Never assume:

```text
moss_20/SPEAKER_01 == moss_40/SPEAKER_01
```

MOSS is **reference evidence**, not absolute ground truth.

Do not automatically merge graph voices solely because MOSS groups them.

---

# 7. Align MOSS to Existing Speech Observations

Before calling the LLM, align MOSS output to the immutable speech ledger.

Use primarily timestamp overlap, with transcript similarity as optional secondary assistance.

Produce mappings such as:

```text
utt_123
original_voice: voice_311
MOSS: moss_40/SPEAKER_03

utt_124
original_voice: voice_732
MOSS: moss_40/SPEAKER_03
```

This creates evidence that:

```text
voice_311
voice_732
```

may belong to the same person.

This should be marked as a possible **mixed voice cluster**.

Do not force a decision.

If an M3 utterance overlaps multiple MOSS speakers, record:

```text
alignment_status: ambiguous
```

rather than choosing the largest overlap blindly.

---

# 8. Evidence Packet for the Strong LLM

At each consolidation point construct one structured evidence package.

Use a configurable strong model such as GPT-6/Astra-class models.

The LLM receives:

## A. Current identity registry

Example:

```json
{
  "person_0": {
    "voice_ids": ["voice_0"],
    "name": "Jake",
    "name_status": "supported"
  },

  "person_1": {
    "voice_ids": ["voice_311"],
    "name": null
  }
}
```

---

## B. Speech observations

Chronological list containing:

```text
utterance
timestamp
original voice ID
Deepgram transcript
current canonical entity, if any
```

Keep transcription source explicit.

Do not treat MAI and Deepgram versions of the same interval as independent evidence.

---

## C. Original speaker-assignment evidence

Include relevant:

```text
CAM++ candidate scores
CAM++ decision

OR 

TST candidate scores
TST decision
```

Clearly distinguish:

```text
historical score
```

from any score recomputed later during consolidation.

---

## D. MOSS alignment

Include:

```text
utterance → MOSS speaker
```

and aggregate summaries:

```text
voice_311:
    8/10 observations → MOSS S03
    2/10 ambiguous

voice_732:
    4/4 observations → MOSS S03
```

---

## E. Existing semantic memory

Provide all semantic memory available **up to the current cutoff**.

Examples of useful information:

```text
voice_311 and voice_732 belong to the same person
voice_643 is Tasha
voice_0 is the camera wearer Jake
```

But label these explicitly as:

```text
model-generated semantic claims
```

not ground truth.

---

## F. Relevant episodic/event memory

Include events necessary for identity reasoning:

```text
"voice_x addresses Katrina"
"the woman in black responds"
"Jake is the camera wearer"
"the same woman continues presenting"
```

Do not feed future memories into earlier historical consolidation runs.

---

# 9. Strong LLM Responsibility

The LLM acts as an **evidence reconciler**.

It should determine:

1. which fragmented voice observations likely belong to the same persistent person;
2. whether an existing voice node appears mixed;
3. whether particular utterances should be reassigned;
4. whether a canonical person can be assigned a real name;
5. whether semantic identity claims conflict;
6. whether there is insufficient evidence.

The model should favor:

```text
defer
```

over an unsupported merge.

---

# 10. Allowed LLM Operations

The LLM must output strict structured JSON.

Support these operations.

## `merge_voice`

```json
{
  "op": "merge_voice",
  "voice_ids": ["voice_311", "voice_732"],
  "target_entity_id": "person_3",
  "evidence_ids": [
    "moss_alignment_18",
    "semantic_740"
  ]
}
```

Meaning:

> These reviewed voice observations are believed to refer to the same persistent person.

Do not delete the original voice nodes.

---

## `reassign_utterances`

Required for mixed or incorrectly assigned voice nodes.

```json
{
  "op": "reassign_utterances",
  "utterance_ids": [
    "utt_125",
    "utt_126"
  ],
  "from_voice_id": "voice_321",
  "target_entity_id": "person_2",
  "evidence_ids": [...]
}
```

This is important because a whole `voice_x` cluster may not be pure.

---

## `set_name`

```json
{
  "op": "set_name",
  "entity_id": "person_3",
  "name": "Katrina",
  "evidence_ids": [...]
}
```

Names belong to canonical people, not individual voice nodes.

Support aliases separately:

```json
{
  "canonical_name": "Lily",
  "aliases": ["Lynn", "Lidi"]
}
```

Do not automatically treat ASR spelling variants as different people.

---

## `resolve_reference`

Resolve semantic/event text referring indirectly to a person.

Example:

```json
{
  "op": "resolve_reference",
  "memory_node_id": 740,
  "mention": "the woman seated on the right",
  "entity_id": "person_3"
}
```

---

## `revise_claim`

Allow clearly incorrect or superseded semantic identity claims to be marked.

```json
{
  "op": "revise_claim",
  "memory_node_id": 504,
  "status": "contradicted",
  "replacement": null,
  "evidence_ids": [...]
}
```

Do not physically erase the original node.

---

## `defer`

```json
{
  "op": "defer",
  "target_ids": ["voice_321"],
  "reason": "Conflicting acoustic and semantic evidence."
}
```

---

# 11. Output Schema

Use a strict schema similar to:

```json
{
  "schema_version": 1,
  "session_id": "egolife_day1",
  "base_graph_version": "...",
  "evidence_cutoff_s": 2400.0,

  "decisions": [
    {
      "decision_id": "d1",
      "op": "merge_voice",
      "voice_ids": ["voice_311", "voice_732"],
      "target_entity_id": "person_3",
      "evidence_ids": ["moss_42", "semantic_740"]
    }
  ]
}
```

The LLM must never return Python mutation code.

It returns only patch operations.

---

# 12. Deterministic Patch Executor

Implement a normal Python executor responsible for graph mutation.

Pipeline:

```text
LLM output
   ↓
JSON schema validation
   ↓
semantic validation
   ↓
conflict detection
   ↓
apply patch
   ↓
save new graph version
```

Validate:

* referenced IDs exist;
* session IDs match;
* evidence is not from the future;
* graph version matches;
* one utterance is not assigned to two canonical people;
* merges do not create known identity contradictions;
* operation dependencies are valid.

If validation fails:

```text
reject operation
log reason
continue with other valid operations
```

Do not crash the entire consolidation run because one decision is invalid.

---

# 13. Canonical Entity Registry

Add a small persistent registry.

Example:

```json
{
  "person_0": {
    "voice_ids": ["voice_0", "voice_364"],
    "utterance_ids": [...],

    "canonical_name": "Jake",
    "aliases": [],

    "name_evidence": [...],

    "created_at_consolidation": 1,
    "updated_at_consolidation": 2
  }
}
```

The registry is the persistent identity layer.

Graph `voice_x` nodes remain as provenance/source observations.

Conceptually:

```text
raw voice nodes
      ↓
canonical person registry
      ↓
retrieval-facing canonical text
```

---

# 14. Updating Memory Text

Do not destructively rewrite original memory text.

Preserve:

```text
raw_text
```

and create:

```text
canonical_text
```

Example:

```text
raw:
<voice_311> suggests making jellyfish lamps.

canonical:
<person_3> suggests making jellyfish lamps.
```

If the name is strongly supported:

```text
Katrina suggests making jellyfish lamps.
```

If identity remains uncertain, keep the original reference.

Never globally run:

```python
text.replace("voice_321", "Katrina")
```

because a fragmented/mixed voice node may contain incorrect observations.

Canonicalization must follow resolved observation/entity provenance.

---

# 15. Retrieval Refresh

After consolidation, rebuild affected retrieval representations.

At minimum refresh:

```text
canonical memory text
dense embeddings
sparse / lexical index
character/entity mappings
Mandol adapter entity references if enabled
```

Do not leave:

```text
new identity graph
+
old retrieval embeddings
```

active simultaneously.

Publish the consolidation patch and rebuilt retrieval state together as a new version.

---

# 16. Historical vs Consolidated Views

Expose both.

## Historical

Shows what M3/TST knew at the original moment:

```text
utt_123
original assignment: voice_732
CAM++ best candidate: voice_311 = 0.51
decision: new voice_732
```

## Consolidated

Shows current interpretation:

```text
utt_123
canonical entity: person_3
name: Katrina
```

Never rewrite historical decisions to make them look as though the canonical identity was known originally.

---

# 17. Consolidation Audit Output

For every run generate a human-readable Markdown audit.

Suggested structure:

```text
# Consolidation @ 40 min

## Existing identities

## MOSS diarization

## Voice/MOSS alignment

## Candidate merges

## Candidate mixed clusters

## LLM decisions

### merge
voice_311 + voice_732 → person_3

Evidence:
- MOSS ...
- semantic node 740 ...
- CAM++ ...

## Names
person_3 → Katrina

## Deferred conflicts

## Graph changes

## Retrieval indexes rebuilt
```

Also save the exact LLM input/output JSON for reproducibility.

---

# 18. Minimal Implementation Structure

Do not over-engineer this into a new framework.

A reasonable structure is:

```text
memory_consolidation/
├── observations.py
├── assignment_logger.py
├── moss_runner.py
├── moss_alignment.py
├── evidence_builder.py
├── llm_consolidator.py
├── schema.py
├── patch_executor.py
├── entity_registry.py
├── canonicalizer.py
├── retrieval_refresh.py
└── audit.py
```

Integrate through wrappers around the existing M3 pipeline.

Avoid major changes to existing M3 construction logic.

---

# 19. First Evaluation Targets

Use the existing EgoLife and M3-Bench memories as regression tests.

### EgoLife 20-minute checkpoint

Test whether the system discovers/supports relationships such as:

```text
voice_0
voice_364
```

without using evidence occurring after the checkpoint.

---

### EgoLife 40-minute checkpoint

Test candidate relationships such as:

```text
voice_311
voice_732
```

and test name grounding cases such as Tasha.

---

### M3-Bench

Test whether existing semantic equivalences propagate correctly into the persistent entity registry.

Also explicitly test contradictory cases around:

```text
voice_10
voice_321
voice_322
```

The system should not blindly transitively merge them.

It should be able to:

```text
reassign observations
reject an unreliable semantic claim
or defer
```

---

# 20. Evaluation Metrics

Do not use reduction in number of voice nodes as the main success metric.

Measure:

```text
false merge rate
identity fragmentation
correctly attributed speech duration
correctly named speech duration
unresolved speech duration
mixed-cluster detection
identity-dependent QA accuracy
retrieval accuracy
```

Also compare:

```text
baseline M3

M3 + MOSS-only consolidation

M3 + strong-LLM semantic consolidation

M3 + MOSS + strong-LLM consolidation
```

This isolates which component actually contributes.

---

# 21. Important Constraints

1. **MOSS is evidence, not ground truth.**
2. **Semantic memories are evidence, not ground truth.**
3. **LLM confidence is not sufficient evidence.**
4. **Do not destructively merge/delete original voice nodes.**
5. **Support observation-level reassignment.**
6. **Names belong to canonical people.**
7. **Never use future evidence in historical consolidation evaluation.**
8. **Keep different videos/session identities isolated.**
9. **Preserve MAI/Deepgram as transcription sources separately from speaker identity.**
10. **Preserve complete historical assignment scores.**
11. **Use deterministic Python code for graph mutation.**
12. **The LLM only proposes structured patches.**

---

# 22. Desired End State

After consolidation, instead of:

```text
voice_311
voice_732
voice_755
voice_...
```

being treated as unrelated speakers, the system should support:

```text
person_3
├── voice_311
├── voice_732
├── selected observations from other fragmented nodes
│
├── canonical_name: Katrina
├── aliases: [...]
├── supporting evidence
└── unresolved/conflicting evidence
```

Then retrieval operates primarily over:

```text
persistent canonical entities
```

while the original M3 graph remains available for provenance.

The primary objective is:

> **Maintain persistent person identity across clips and allow later evidence to repair earlier identity mistakes without destroying the original memory history.**
