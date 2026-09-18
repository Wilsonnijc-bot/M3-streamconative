# Automatic M3 + Mandol publication

The combined cycle passed on the saved 20-minute recall round-1 decisions.
No new Astra call was made. Results: [verification and replay](runs/deployment_cycle/README.md).

`pipeline.publish` → `native.publish_native` stages native character write-back,
canonicalizes retrieval text, and re-embeds changed native text through the configured
M3 backend. `reindex_cycle.build_retrieval_bundle` then exports canonical memories
and runs `mandol_worker` to build Mandol dense, BM25, and SPLADE indexes. The worker
reloads every memory and its embeddings and runs a hybrid search. Only after all
checks succeed does publication advance `CURRENT.json`. Any failure leaves the
previous published version available; the failed build log is retained.

The completed version is
`v_66eb04de45183ff45dd782fdfb306defbbc592fc4b50113983c2c626420e53d7`.

| Check | Result |
| --- | --- |
| Native changed text nodes re-embedded | 105 |
| Native untouched embedding collections | 384 (278 text, 106 voice) |
| Raw contents and graph edges | Unchanged |
| Mandol memories verified after reload | 383 |
| Mandol dense / BM25 / SPLADE | Passed |
| Hybrid retrieval before publication | 3 results |
| Published-reader query, `What did Jake do?` | 3 results |
| Published hashes after querying | Unchanged |
| Validation process exit | 0 |

Native M3 reindexing is selective. Mandol currently rebuilds its complete text
retrieval bundle (including 21 native character entities) in the staged version.
It does not change native audio, face, or image embeddings. No separate indexing
timer or manual Mandol interval is required.

## Runtime configuration

Public Mandol embedding settings are in `deployment.json`; override the file with
`CONSOLIDATION_DEPLOYMENT_CONFIG`. Credentials remain in the runtime environment.
Set `MANDOL_PYTHON` to the installed Mandol Python runtime. `MANDOL_WORKDIR` defaults
to this repository's `Mandol` directory; installed relative model paths must resolve
there. The first attempt failed because that directory lacked the existing SPLADE
checkpoint. The retry reused the installed checkpoint through a local symlink.
Its actual weights are `naver/splade-cocondenser-ensembledistil`, installed under the
deployment alias `naver/splade-v3`; see `metadata/splade_checkpoint_source.json` in
the results. No gated model was downloaded.

For current-version retrieval, pass the publication **session directory** containing
`CURRENT.json` to M3 retrieval or to `M3MandolRetriever.load`. M3 loads a verified
version for each request; Mandol detects a changed pointer at query entry and pins
one loaded version for that query. Explicit graph objects or version paths remain
pinned. Published Mandol files are copied to a temporary runtime directory before
loading so cache writes cannot modify the immutable version.

## Tests and deployment boundary

49 consolidation tests, 41 M3 tests, and 2 Mandol publication tests passed in their respective working
directories. Tests cover failed native/Mandol embedding rollback, wrong-version
readiness rejection, nested artifact tampering, and native pointer loading across
successive publications. Mandol publication tests cover integrity rejection and
switching readers without changing human-name queries.

This validates automatic reindexing for a consolidation snapshot. The subsequent
[live runtime](RUNTIME.md) adds asynchronous reasoning, native identity reconciliation
between clip writes, and background index replacement while construction continues.
It never replaces the live graph with the historical published checkpoint.
