# Reusable preprocessing cache

This archive holds the Jake artifacts that do not depend on the VLM backend:

- Deepgram ASR output and segmented-audio references.
- Face detection and face-recognition output.
- CAM++ voice mappings for C1 and TST voice mappings for C2–C4, including their provider-side records.
- The source schedule, source hashes, and current run manifest.

Each condition's original `intermediate` path is a compatibility symlink to its archived directory. The online runner therefore reuses these artifacts without configuration changes when a new VLM backend is selected.

VLM-derived memories, graph snapshots, Mandol indices, retrieval outputs, and consolidation artifacts are intentionally outside this archive and must be rebuilt for a new backend.
