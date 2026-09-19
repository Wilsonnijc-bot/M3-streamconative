# Offline entity memory consolidation

[Live runtime](RUNTIME.md): asynchronous snapshots, clip-boundary native identity
commits, hot-memory retrieval, and background selective reindexing. Existing
consolidation decision logic is reused unchanged.

The [automatic M3 + Mandol cycle](AUTOMATIC_REINDEX.md) is validated: native reindexing,
Mandol dense/BM25/SPLADE rebuild, reload checks, and atomic publication all run within
consolidation, with no separate indexing interval.

The current publication path writes accepted conclusions into **native M3 characters**,
preserves raw evidence, and selectively updates M3's existing text embeddings.
See [the native integration report](NATIVE_CHARACTER_INTEGRATION.md) for exact call paths,
stable IDs, mixed-feature scopes, tests, and [real integration results](runs/native_character/README.md).
Use `--native-graph /path/to/graph.pkl` for the first publication. Later publications
use the current native graph. Embeddings use the existing configured M3 backend.

**Validated locally:** EgoLife 20/40-minute historical replay, M3-Bench replay,
recorded-patch execution, version succession, failure handling, and HTTP transport
contracts and native character integration. **Not yet measured:** independent identity
accuracy. The historical regression patches are authored test inputs, not model
discoveries; their token-hash vectors are test fixtures, not native production embeddings.

[Inspectable regression outputs](runs/regression/README.md) ·
[System prompt](prompts/system.md) · [Validation notes](VALIDATION.md)

## Setup and tests

From the repository root, Python 3.9 or later:

```bash
python3 -m venv consolidation/.venv
consolidation/.venv/bin/python -m pip install -r consolidation/requirements-native.txt
consolidation/.venv/bin/python -m pytest consolidation/tests -q
consolidation/.venv/bin/python -m consolidation.regression --output /tmp/consolidation-regression
```

The regression output directory must be fresh. It produces a single README index,
three versioned audits/graphs, exact prompt and recorded response artifacts, and a
machine-readable report. Model weights and source media are not copied into it.

## Replay → packet → patch → version

```bash
consolidation/.venv/bin/python -m consolidation prepare \
  --native-graph /path/to/current_native_graph.pkl \
  --cutoff 1200 --work consolidation/runs/metadata/egolife_20
```

The requested 1200 s cutoff selects the saved graph ending at **1187.92 s**.
2400 s selects **2387.92 s**. Times in observations and MOSS outputs are relative
to the session origin (DAY1 11:09:42.08), not execution wall-clock time. No final
snapshot is filtered backwards. The metadata loader intentionally reads only
committed segments through the requested boundary and rejects out-of-prefix memories.

Each packet contains the existing registry, chronological observations with separate
MAI/Deepgram fields, assignment provenance, MOSS alignment if supplied, all semantic
and episodic memories through the cutoff, and evidence IDs. Semantic/event text is
explicitly model-generated. Ambiguous historical assignments remain null.

For a recorded strict JSON patch:

```bash
consolidation/.venv/bin/python -m consolidation run \
  --native-graph /path/to/current_native_graph.pkl \
  --cutoff 1200 --work consolidation/runs/metadata/egolife_20 \
  --patch /path/to/patch.json
```

For a configured strong model and semantic embeddings, set `CONSOLIDATION_API_KEY`
in the environment and supply model IDs actually available from your provider:

```bash
consolidation/.venv/bin/python -m consolidation run \
  --native-graph /path/to/current_native_graph.pkl \
  --cutoff 1200 --work consolidation/runs/metadata/egolife_20 \
  --endpoint https://YOUR_PROVIDER/v1 --model YOUR_STRONG_MODEL \
  --moss-json consolidation/runs/metadata/moss_20/moss.json
```

Endpoints follow the chat-completions / embeddings JSON protocols. No API key is
written to artifacts. All evidence is sent to the explicitly configured endpoint.
JSON mode plus the supplied schema is used; every decision is validated locally.
The model returns data only. No `eval`, `exec`, or generated mutation code is used.

Native publication uses M3's configured text embedding backend. A failed embedding
call prevents version publication. Hash vectors remain confined to historical tests.
Use one output root for successive checkpoints; the 40-minute run automatically
loads the current native character state. New observations may receive provisional
scoped assignments under the strict >75% admission rule described in the integration report.
A stale patch/base or session mismatch aborts the run;
invalid individual operations are rejected and audited while valid peers continue.

M3-Bench uses the same importer, with explicit metadata and an isolated namespace:

```bash
consolidation/.venv/bin/python -m consolidation prepare \
  --native-graph /path/to/current_native_graph.pkl \
  --root m3bench_bedroom_01 --session m3bench_bedroom_01/gemini --cutoff 2400 \
  --metadata m3bench_bedroom_01/provenance/raw/gemini/results/memory/q11_uncompressed/metadata.json \
  --work consolidation/runs/metadata/m3bench
```

That metadata's last committed segment ends at 1265 s; the requested time never
fabricates additional committed coverage.

## Full-prefix MOSS

The implementation follows the upstream [MOSS model card](https://huggingface.co/OpenMOSS-Team/MOSS-Transcribe-Diarize).
Configure a MOSS transcription server separately. No GPU instance is launched or
rented by this package. With source clips and `ffmpeg` available:

```bash
consolidation/.venv/bin/python -m consolidation moss \
  --cutoff 1200 --work consolidation/runs/metadata/moss_20 \
  --media-root egolife_day1 --moss-endpoint http://localhost:8000/v1 \
  --moss-revision YOUR_DEPLOYED_CHECKPOINT_REVISION
```

This writes a 16 kHz mono WAV covering the entire committed prefix, preserving
source-clock gaps as silence. It requests `verbose_json` and saves raw output,
normalized speaker segments, model/revision/configuration and audio SHA-256.
Repeat at 2400 s for the complete 40-minute prefix; do not concatenate separately
diarized windows or equate their speaker labels. Imported `moss.json` needs:

```json
{
  "session_id": "egolife_m3_jake_day1/gemini",
  "run_id": "egolife_m3_jake_day1/gemini/moss_20",
  "cutoff_s": 1187.92,
  "segments": [{"start": 0.5, "end": 2.0, "speaker": "S01", "text": "example"}]
}
```

Overlap with multiple speakers remains ambiguous even when one overlap is larger.
MOSS alone cannot authorize a merge. Its suggestions and mixed-cluster summaries
are hypotheses for the reconciler. Imported outputs must match the exact session
and committed cutoff; future segments are rejected.

## Online assignment evidence and schedule

`online.assign_observation` is the opt-in replacement for the small voice
search/add/update block in `process_voices`. Pass the real ordered `VideoGraph`,
`AssignmentLogger`, `ObservationLedger`, clip/index, session-relative start time,
audio reference and run ID. It logs every existing CAM++ candidate and full-precision
score before graph mutation, including rejected candidates and the original threshold,
model/configuration and graph fingerprint. It then records the resulting voice ID in
the immutable observation. Existing M3 modules are not modified by importing this package.

Use `AssignmentLogger.record(method='TST', ...)` for enrolled-identity scores. Pass
the fixed enrollment gallery and each candidate's eligibility/rejection status;
`non_target` is stored as rejection, never a canonical identity. Keep transcript
compensation/grouping in `intermediate`. Numeric CAM++/TST scores remain separate.
Supply the resulting JSONL via `--assignment-jsonl` to include it in a packet.

`CommitScheduler.committed(end_time)` runs at the first complete segment reaching
each approximately 20-minute boundary; call with `final=True` at end of input.
`replay.schedule` instead selects saved commits at or before requested historical
boundaries and adds the final commit. Persist scheduler state with the online job.

**Historical limitation:** the supplied caches were saved before voice matching;
the voice embedding pool also randomly subsampled old embeddings. Exact original
candidate scores cannot be reconstructed from these files. The importer uses unique
new transcript occurrences in consecutive graph snapshots to recover assignments,
marks collisions ambiguous, and labels historical scores `not_recorded`. It never
presents newly calculated scores as historical observations. Cached media remains
referenced by source path and row; transcript variants remain one observation.

## Historical stage-one mutation and retrieval contract

This section describes the retained person-based regression artifacts. New CLI
publications use native characters and M3 retrieval, as documented in the integration report.

`schema.py` defines strict schemas for merge, reassignment, naming/aliases, scoped
reference resolution, claim revision, and defer. New people are created by a merge
or reassignment operation. Dependencies must precede their consumers. Known
`cannot_link` constraints can reference voices, utterances, or canonical people;
they must come from reviewed input, not a fabricated ground-truth assumption.
MOSS mixed clusters require observation-level handling. Duplicate decisions,
unknown IDs, future evidence, contradictory assignments and unsupported names are
rejected per operation with no partial mutation. Revising the only claim supporting
a name revokes that name. Later runs can correct scoped reference resolutions.

Original memory text remains `raw_text`. `canonical_text` uses explicit
`resolve_reference` decisions or a memory's proven `utterance_ids`. The historical
M3 exports do not bind text nodes to exact observations, so simply merging two voices
does **not** globally replace their IDs throughout memory text. The reconciler must
resolve relevant mentions. Contradicted/superseded original claims are retained but
excluded from active retrieval. Claim replacement text is preserved as audit data;
it does not become an independently verified memory.

Each session has its own hashed directory and append-only observation ledger.
`versions/v_<hash>/` contains graph, state, evidence, patch, execution report,
historical/consolidated views, audit and retrieval. Raw graph nodes remain intact;
`canonical_entities`, `utterance_assignments`, `identity_edges` and
`canonical_memories` expose the consolidated graph layer. Retrieval includes dense
vectors, lexical postings, entity mappings and namespaced Mandol reference exports.

A lock, staging directory, content hashes and atomic `CURRENT.json` replacement
publish graph and retrieval together. Readers should resolve `CURRENT.json` once
and load both files from that version; `load_current` validates file integrity.
`retrieval_refresh.search` queries the version-local index with the matching embedder.
This is a standalone retrieval surface; it does not silently change the existing
StreamMeCo/Mandol running processes or their old indexes. Mandol reference exports
can be consumed by an enabled downstream adapter.

## Evaluation

`evaluation.evaluate` accepts independent observation-level gold:
`{utterance_id: {"person_id": "gold_identity", "name": "optional name"}}`.
It measures pairwise false merges, fragmentation, one-to-one attributed duration,
named/unresolved duration and mixed-cluster precision/recall. Supply independently
scored QA/retrieval outcomes to report their accuracy. Unmeasured outcomes stay null.
For more than eight identity clusters, install `scipy` for Hungarian matching;
without it, attributed duration is null rather than a misleading greedy estimate.

`baseline_state` builds the original voice-cluster baseline. `compare_variants`
compares `baseline_m3`, `moss_only`, `semantic_llm`, and `moss_semantic_llm` states,
marking missing runs `not_run`. MOSS-only experiments still require explicit recorded
patches and the same executor; alignment never silently merges identities.

Live MOSS, strong-LLM judgments, production semantic retrieval quality, and the four
model-quality ablations require configured models and independent identity/QA labels.
The current regression demonstrates implementation behavior, not their accuracy.

## Real Hyperstack MOSS and official Astra runs

`moss_local.py` supports pinned, locally downloaded MOSS weights on a CUDA GPU.
`consolidation/scripts/run_moss_hyperstack.sh` records an exit status and durable log
for the two complete prefixes in a detached tmux job. Model inputs, WAV hashes, raw
outputs, normalized segments, checkpoint revision and runtime versions are retained.
Any invalid or out-of-input timestamp predictions are explicitly recorded as anomalies;
they are excluded or bounded to the audio actually supplied, never future audio.

`live_run.py` reads the `gpt-6-astra` entry of the existing API config without
copying its credential into artifacts. Empty `base_url` selects
`https://api.openai.com/v1`; a nonofficial hostname is rejected. It uses the Responses
API with high reasoning effort from config, saves the background response ID, and
can resume that same request rather than issuing a duplicate paid request. Exact
requests and raw completed responses are retained. Native text reindexing uses the
existing configured M3 `text-embedding-3-large` backend and its configured credential.

After syncing MOSS results into `runs/live/moss/prefix_20` and `prefix_40`:

```bash
consolidation/.venv/bin/python -m consolidation.live_run --minutes 20 --native-graph /path/to/current_native_graph.pkl --output consolidation/runs/native_live
```

Astra accepts the MOSS-derived transcripts and speaker/timestamp evidence, not raw
audio. The raw WAV files remain on the GPU machine with their hashes in the evidence.
[Live run outputs](runs/live/README.md) are separate from the authored regression.

## Exact replay review folder

[Open the per-checkpoint review index](runs/live/review/README.md) for the byte-preserved historical replay, exact decoded MOSS transcript, complete Astra instructions and evidence input, and unedited Astra output. Original API request/response JSON and source graph JSON are in each checkpoint’s `metadata/` with a SHA-256 manifest. Pending artifacts are labeled pending, never substituted with fixtures.

## Recall-oriented consolidation

The current policy infers a person per voice/cluster, propagates to the reviewed
observations, and handles contrary utterances as explicit exceptions. `assign_cluster`
requires confidence, rationale, evidence IDs and an exception list. A possible mixed
MOSS cluster is advisory for this operation, not an automatic refusal. Existing
conflicting assignments and cannot-link constraints still block defaults; explicit
`reassign_utterances` is needed to correct identities. Native construction can admit
new observations provisionally under the >75% rule. Assignment history preserves IDs, reasons,
confidence and evidence; published versions remain independently recoverable.

The evidence packet includes cluster inventory, unresolved counts, existing defaults,
assignment metadata and the previous round's accepted/rejected decisions. Astra reviews
all unresolved clusters, including fragments, using contextual support rather than
requiring an identity proof from every short utterance. Coverage is not identity accuracy.

The completed historical two-round results and exact review artifacts are retained
under `consolidation/runs/recall_20/`. The native integration reuses the accepted round-1
conclusions; it does not request another Astra response.
