# Native M3 character write-back

The subsequent [automatic retrieval cycle](AUTOMATIC_REINDEX.md) also verifies
Mandol dense, BM25, and SPLADE readiness before publishing the native graph.

Implemented and validated against the saved 20-minute recall **round-1** conclusions.
No new Astra call was made. The original native checkpoint was fetched from the existing
Hyperstack experiment and retained unchanged. Runtime retrieval uses native M3 characters.

## 1. Files changed

Native implementation:

- `StreamMeCo/mmagent/character_identity.py`: character resolution, scoped assignments,
  stable merges, observation admission, canonical text, and selective reindexing.
- `StreamMeCo/mmagent/videograph.py`: native methods, construction hooks, refresh protection,
  stale-index protection, and historical-cutoff guard.
- `StreamMeCo/mmagent/retrieve.py`: native canonical result text and unchanged name queries.
- `StreamMeCo/mmagent/memory_processing.py`, `memory_processing_qwen.py`, and
  `StreamMeCo/m3_agent/memorization_memory_graphs.py`: canonicalization before embeddings,
  including the shared Gemini/Qwen precomputed-batch path.
- `StreamMeCo/m3_agent/export_mandol.py` and `StreamMeCo/mmagent/clip_audit.py`: native
  character export, scoped references, and persisted identity audit fields.
- `StreamMeCo/mmagent/__init__.py` and `utils/__init__.py`: lazy submodule imports so native
  graph loading does not initialize GPU perception models. Qwen generation imports are
  also deferred until generation is actually requested.

Consolidation integration:

- `consolidation/native.py`, `pipeline.py`, `__main__.py`, and `live_run.py`: native
  preparation, write-back, configured embedding use, and transactional publication.
- `consolidation/schema.py`, `patch.schema.json`, `patch_executor.py`, `entity_registry.py`, `replay.py`, and
  `prompts/system.md`: optional exact reference occurrences, original content boundaries,
  and native-character proposal semantics.
- `consolidation/native_fixture.py`, `tests/test_native_characters.py`, and
  `requirements-native.txt`: repeatable integration verification and native runtime tests.

Existing unrelated worktree changes were preserved.

## 2. Native character state

`character_mappings` still maps `character_N` to a feature list. Its reverse dictionary is
derived only from that current mapping. Additional native state contains:

- `character_metadata`: canonical name, aliases, minimum available assignment confidence,
  name/support evidence, merged character IDs, and consolidation provenance.
- `observation_character_mappings`: observation ID to native character ID.
- `reference_character_mappings`: original memory node/content-index/span to a native
  character ID, exact mention, and supporting evidence.
- `identity_observations` and `reviewed_feature_support`: native observation records,
  reviewed votes, coverage, and provisional status.
- Identity revision, cutoff, session, history, retired IDs, and a monotonically increasing
  character-ID allocator.

All fields persist through ordinary native graph pickling. Old pickles need no migration
until consolidation is applied. There is no pre-consolidation mapping stored as a fallback.

## 3. Consolidation write-back

`pipeline.prepare` reconstructs transient proposal aliases from the current native graph.
`pipeline.publish` routes native inputs to `native.publish_native`, which executes the
existing validated patch, copies the native graph, projects accepted conclusions into
native character operations, reindexes changed text, and stages a new version.

The published version includes `graph.pkl`, native review JSON, change and embedding
reports, and exact model artifacts. `proposal_audit.json` retains the temporary proposal
state for inspection only. Retrieval never reads it. `CURRENT.json` advances after every
required artifact and vector has been successfully written. An embedding failure or stale
base leaves the previous version current.

## 4. Stable character selection

An explicitly associated existing native character survives when compatible. Otherwise,
the supported observation overlap selects an existing compatible character, with the
lowest numeric ID breaking ties. Existing associations are reserved before incidental
overlap is considered. New IDs are allocated only when no compatible survivor exists.

An affected legacy character is retired only when it has no remaining global features or
scoped observation assignments and its moved support identifies one survivor. Partially
moved characters and unrelated characters remain. Retired IDs are never allocated again.
Merge lineage is provenance, not a resolver fallback.

## 5. Mixed features and new observations

Only complete, unanimously assigned reviewed features receive global ownership. Mixed,
unresolved, incomplete, and historically ambiguous candidate features have no authoritative
global mapping. Their supported observations and memory occurrences remain scoped.

Appending evidence through `VideoGraph.update_node` invalidates global completeness. New
observations may receive a provisional scoped assignment only when independent reviewed
votes exceed **75% of all known observations**. Exactly 75% is unvalidated; inherited
assignments never cast votes. Native admission IDs use `feature/content_index` when the
construction caller has no external observation ID. The next complete prefix review
replaces these admission records with reviewed observation IDs.

An unscoped mixed-feature mention remains raw regardless of its majority. Explicit
observation assignments take priority over occurrence assignments, then current global
ownership, then raw identity. A resolved unnamed character displays `character_N`.

## 6. Exact retrieval path

`retrieve_from_videograph` -> `back_translate` (identity-preserving for consolidated
queries) -> existing configured query embedding -> `VideoGraph.search_text_nodes` ->
existing clip/node ranking -> `search` result assembly -> `translate(..., node_id=...)` ->
`character_identity.canonicalize_contents` -> `resolve_identity`.

`VideoGraph.resolve_identity` exposes the same resolver for observation-aware callers.
The resolver returns feature ID, native character ID, canonical name, display identity,
resolution source, and provenance. Scoped identities can lack global features, so the
consolidated retrieval path searches the native text index without the old raw-feature
prefilter. No parallel search/index implementation was added.

Mandol exports use this resolver and canonical text. They do not infer mixed-feature
identity from adjacent graph edges or resurrect retired characters from raw mentions.

## 7. Canonicalization before embedding

The shared construction batch now calls `prepare_texts` before `get_embeddings_batch`.
`process_memories` also canonicalizes on its direct-embedding path. Precomputed handoffs
must identify their exact canonical input; raw-text vectors cannot be silently attached
to canonical text. The legacy memory-processing path uses the same preparation helper.

Text nodes retain immutable `metadata['contents']`, with separate `retrieval_contents`,
`retrieval_identity_trace`, and `embedding_input_fingerprint`. Their existing
`node.embeddings` is the retrieval vector collection. Raw voice/face contents and
embeddings are not canonicalized.

## 8. Reindexing

Native publication invokes `reindex_text`. It compares each new canonical representation
with the text used by its current vectors, batches only changed text, validates vector
counts/dimensions/finiteness, then updates those text nodes. The configured M3 alias is
`text-embedding-3-large`; this workspace currently routes it to OpenRouter's
`openai/text-embedding-3-large`. Provider credentials are read from the existing runtime
environment and were not stored in result artifacts.

Construction invalidation marks identity text dirty. Before subsequent construction
embedding or native search, the existing index is brought current. Dirty graphs cannot
be exported. Backend failures cannot cause stale vectors to be served as updated ones.

## 9. Repeated consolidation and refresh

The next run reconstructs proposal inputs from native metadata and scoped assignments,
not the previous person registry. It can update names, merge characters, move newly safe
features, remove reviewed observation/reference assignments, and retain minority exceptions.
Extended native graphs retain their new construction nodes through publication.

`refresh_equivalences` and `order_character` preserve consolidated state and do not replay
construction equivalence claims over established identities. Claims remain raw evidence
for a later consolidation. Earlier-cutoff retrieval must select an earlier immutable
version; truncation cannot reuse a later identity conclusion.

## 10. Tests and real results

**55 tests passed** across consolidation tests, native architecture tests, legacy Mandol
export tests, and graph Markdown tests. Coverage includes merges, partial moves, name
correction, face/voice scopes, repeated occurrences, strict majority boundaries, refresh,
reload, repeated/later-prefix publication, query preservation, selective embeddings,
failure rollback, stale bases, legacy compatibility, and operation without importing
consolidation or GPU runtimes.

Real round-1 fixture:

| Result | Value |
| --- | --- |
| Supported consolidated native characters | 4 |
| Named characters | `character_0`: Jake; `character_41`: Xiu Shuo |
| Unnamed consolidated characters | `character_12`, `character_53` |
| Scoped observation assignments | 216 |
| Globally safe features | 87 |
| Mixed/incomplete features excluded from global ownership | 19 |
| Retired character IDs | 85 |
| Explicit reference occurrences | 43 |
| Re-embedded text nodes | 105 of 383 |
| Unchanged text embedding collections | 278 |
| Unchanged voice embedding collections | 106 |
| Raw contents and edges | Preserved exactly |

The fixture has no face nodes; native synthetic tests cover face mapping and mixed faces.
These checks validate application of accepted conclusions, not independent identity accuracy.

[Integration artifacts](runs/native_character/README.md) include original/canonical text,
resolution traces, native pickle, export, and per-node before/after embedding hashes.
[Verification](runs/native_character/verification.json) records the unchanged source hash
and the published immutable version. The initial missing-local-credential failure is
retained in metadata; it published nothing. The successful run used the existing remote
runtime credential in process memory through the unchanged configured backend.

To apply another saved accepted run, use `python -m consolidation.native_fixture` with
`--source-graph`, `--accepted-version`, and `--output`. To verify an existing publication
without embedding calls, add `--verify-existing`. Normal live runs now require a native
graph for the first publication, then use the current native version thereafter.
