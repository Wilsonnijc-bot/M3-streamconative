# Stage-one validation

Validated 2026-09-17 from the repository root using the isolated Python environment
in `consolidation/.venv`. All implementation changes are under `consolidation/`.
The existing M3 source files, saved graphs, caches and user changes were not edited.

## Results

`consolidation/.venv/bin/python -m pytest consolidation/tests -q`

**24 passed.** Coverage includes:

- Immutable observation replay, transcript-source preservation and session isolation.
- Every allowed patch operation, per-operation rejection, dependencies and duplicate IDs.
- Stale versions, future/foreign evidence, unsupported names, mixed clusters,
  known cannot-link conflicts, and non-destructive observation reassignment.
- Name revocation after its only supporting claim is contradicted.
- Conservative canonical text and exclusion of revised claims from active retrieval.
- Atomic graph/retrieval publication, deterministic version content, persistence
  across checkpoints, integrity checks and embedding failure before publication.
- Complete pre-mutation CAM++ logging, first-voice creation and TST fixed-gallery
  enforcement across logger restarts; non_target remains a rejection.
- Full-prefix audio duration and silence at source-clock gaps, run-scoped MOSS
  speaker alignment and ambiguity handling.
- Chat, MOSS and embedding HTTP serialization against a **local test server**.
  These tests invoke no actual models.
- Duration/fragmentation/false-merge metrics and scheduling/finalization behavior.

## Real-artifact regression

Run `python -m consolidation.regression` with a fresh output directory.
[Inspect generated audits and versions](runs/regression/README.md).

| Source | Actual committed cutoff | Observations | Memories | Accepted / rejected |
| --- | ---: | ---: | ---: | ---: |
| EgoLife nominal 20 min | 1187.92 s | 224 | 383 | 4 / 0 |
| EgoLife nominal 40 min | 2387.92 s | 421 | 774 | 4 / 1 |
| M3-Bench selected metadata prefix | 1265.00 s | 131 | 405 | 2 / 1 |

The EgoLife 40-minute version descends from the 20-minute version. M3-Bench has its
own session namespace. Two EgoLife observations have ambiguous historical voice
assignments and remain explicitly unresolved. No speech-cache gaps were found in
these selected prefixes. Cache SHA-256 values and source graph versions are retained.

The authored patches exercise Jake naming from semantic node 372, the
voice_311/voice_732 equivalence claim in node 740, and Tasha naming from node 654.
An unsupported Katrina name is rejected. The 20-minute run defers voice_0 instead
of presuming it equals voice_364. M3-Bench tests an injected cannot-link constraint
around voice_10/voice_321; this constraint is test input, not a discovered label.

These are executor/contract tests grounded in real artifacts. Accepted operations
are **not** evidence that the underlying model-generated claims are correct.
No actual LLM generated the regression patches. No actual MOSS inference was run.
The dense index in this regression is the named local token-hash baseline.

## Iterations made during validation

- Added M3-Bench's different speech-cache directory layout.
- Kept duplicate transcript-to-voice mappings ambiguous instead of selecting one.
- Revoked unsupported names when their supporting claim was revised.
- Allowed later scoped reference corrections while rejecting within-patch conflicts.
- Pinned TST gallery identity across process restarts.
- Added source-cache hashes and guarded against missing previously assigned observations.

## Remaining model-quality evaluation

The implementation provides MOSS and configurable strong-LLM transports, semantic
embedding backends, and an evaluation interface for the four requested variants.
Live quality evaluation needs deployed endpoints/model IDs and independent identity,
QA and retrieval labels. No live endpoint was configured for this run, and no GPU
resources were provisioned. Those accuracy metrics remain unmeasured.

Exact historical CAM++ candidate scores are absent from the supplied source caches.
The original random embedding-pool sampling prevents faithful score reconstruction.
Historical outputs state `not_recorded`; future online logging captures complete
candidate evidence before mutation. Missing scores were not fabricated.

## Recall-oriented policy revision (2026-09-17)

29 tests pass. Added tests exercise propagation to non-anchor utterances, mixed-cluster
exceptions, confidence/provenance persistence, explicit corrections with previous-person
history, out-of-scope exceptions, conflicting defaults and cannot-link rejection.
The saved JSON schema is regenerated from the runtime schema.

The two live 20-minute rounds are recorded separately under `runs/recall_20`.
`python -m consolidation.verify_recall` validates their published hashes, sequential
registry lineage, unchanged source nodes/edges, unchanged MOSS input, cutoff boundaries,
3072-dimensional official embeddings, and byte-exact request/output review copies.
Coverage gains do not establish identity precision; no independent gold labels exist.

Live outcome: round 1 assigned 216/224 observations (71 accepted, 4 rejected decisions);
round 2 retained 216/224 (18 accepted, 0 rejected). Named assignments: 152. Resolved
memory references: 4 baseline, 42 round 1, 55 round 2. Both live verifications passed.
Two of the eight unresolved observations have null source voices, which the current
reassignment schema cannot address; this limitation is recorded in the result README.
# Native M3 character integration

55 focused and regression tests pass, including the actual native retrieval and
construction paths, character refresh, later-prefix publication, scoped face/voice
assignments, export, stale-base rejection, and embedding-failure rollback.
The saved 20-minute recall round-1 conclusions were applied through native publication
using M3's configured OpenRouter text embedding backend. All 216 assignments survived;
105 text nodes were re-embedded and 384 embedding collections were unchanged. Raw
contents and edges were preserved. See [the complete report](NATIVE_CHARACTER_INTEGRATION.md)
and [the real verification](runs/native_character/verification.json).
