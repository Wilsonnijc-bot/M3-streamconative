# Compact incremental consolidation

The model receives new evidence after the previous successful committed clip boundary,
plus compact native characters and selected original historical evidence. Every call is
a fresh request. Previous model decisions and rationales are not replayed. The full
prefix remains available internally for provenance, validation, and native projection.

## Packet and budgets

`prompt_packet.build_prompt_packet` returns the model view, execution scope, and size
report. `prepare_prompt` establishes the internal scope and saves three artifacts:

- `prompt_packet.json`: the exact user evidence object serialized into the request.
- `prompt_scope.json`: allowed new observations, historical correction targets, memories,
  voices, characters, and citable evidence IDs.
- `prompt_size.json`: compact UTF-8 byte sizes by section, historical selections and
  omission counts, and prompt-format version 2.

Both model transports and CLI preparation use this builder. `evidence.json` retains
the full internal records. Native publications copy the prompt artifacts into the
version manifest alongside exact request/response artifacts.

Operational paths, hashes, runtime configuration, and redundant session/version fields
are omitted through an explicit allowlist. Original evidence text is preserved, including
anything naturally occurring in that text. ASR alternatives share text only when exactly
equal. Distinct utterances remain distinct. Memories retain ordered content strings for
exact reference offsets. MOSS segments occur once, with alignments referring to segment
IDs; labels are scoped to the current MOSS run. CAM++/TST candidate scores remain separate.

Historical selection offers each character up to two observations and two memories,
prioritizing name support, shared voices/current-run MOSS speakers, and recency. Selection
proceeds round-robin before additional anchors. Up to 16 linked unresolved/conflicting
turns and 16 turns from the previous 30 seconds supply correction and boundary context.
Overlapping selections are deduplicated. Their dependent MOSS, assignment, and reference
records count toward the historical budget. Oversized historical records are skipped,
never truncated. All new observations and memories are retained.

Defaults, configurable through environment variables:

| Setting | Default | Meaning |
| --- | --- | --- |
| `CONSOLIDATION_HISTORY_BYTES` | 65536 | Historical record budget; zero disables historical anchors |
| `CONSOLIDATION_PACKET_BYTES` | 524288 | Complete compact user packet budget |

These limits measure bytes, not model tokens, and exclude system instructions/schema.
The mandatory character registry can grow with the number of identities. A packet that
exceeds the total budget fails before API submission with saved section-size diagnostics.
New evidence is never silently removed to make it fit. Adjust the cadence/budget and
retry an oversized window after inspecting the diagnostic. A model request already
submitted to the official transport can only resume with its identical saved payload.

## Decisions and native state

With an execution scope, `assign_cluster` and `merge_voice` affect only the new window.
`reassign_utterances` can explicitly correct supplied historical observations. Memory
references and claim revisions require supplied memories; all cited evidence must be
visible. Naming and contradiction checks still apply. Names update native character
metadata and consequently affect its existing references.

Accepted decisions update the full internal state before native projection, preserving
omitted observations, mixed-voice vote counts, references, and character lineage. The
executor's optional `scope` argument, or the packet's internal `_execution_scope`, enables
this enforcement. Legacy direct executor calls without scope remain available for
historical recorded-patch replay; production transports and the native worker set scope.

The [runtime](RUNTIME.md) preserves each 20-minute boundary with one active and one waiting
snapshot, applies backpressure, and drains a final partial window on shutdown. A failed
window retains its place for explicit retry. MOSS transcribes the same new audio interval
before reasoning: 0-20, 20-40, then 40-60 minutes, aligned to actual committed cutoffs.
Its local timestamps are converted to session time. Historical anchors use their existing
text, with no alignment in the new MOSS run. Older speaker labels cannot be equated with
the new run's labels. Full internal graph/evidence storage still grows with the session.

## Size comparison

Rebuilding the saved `recall_20` packets as first-window requests, retaining all 224
observations and 383 memories, produces approximately:

| Saved input | Original compact bytes | New compact bytes | Reduction |
| --- | ---: | ---: | ---: |
| Round 1 | 807542 | 267000 | 67% |
| Round 2 | 1189907 | 270000 | 77% |

This comparison isolates deduplication and metadata removal from incremental historical
selection. The historical rounds actually re-reviewed the same 1187.92-second prefix;
they are not evidence of 20/40/60-minute model performance under the new policy.
Tests exercise those window transitions and bounded growth with mocked/recorded decisions.
No new paid inference or independent identity-accuracy measurement is implied.
