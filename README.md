# M3-streamconative

## Architecture

<p align="center">
  <img src="architecture.png" alt="M3-streamconative architecture" width="100%">
</p>

---

Multimodal streaming memory with callable compression and two alternative, controller-free retrieval paths.

M3-streamconative builds structured memory from video clips and their audio. It retains episodic, semantic, voice, and face information together with character mappings and temporal indexes. Retrieval uses either the native M3 path or an adapter into Mandol’s built-in hybrid retrieval stack.

Documentation basis: this draft reflects the maintainer’s pipeline description. The repository could not be fetched during preparation, so implementation status is maintainer-reported rather than code-audited. Module paths, installation commands, exact model names, and backend defaults are deliberately not invented.



Architecture and design contracts · Vector diagram · Mermaid source

Pipeline at a glance

Video clip + associated audio
    → M3 memory construction
    → Shared multimodal memory
        ├─ Episodic nodes
        ├─ Semantic nodes
        ├─ Voice nodes
        ├─ Face nodes
        ├─ Character mappings
        └─ Temporal indexes
    → Use raw memory OR explicitly invoke StreamMCCO compression
    → Prepare the selected retrieval backend
        ├─ Native M3 retrieval
        └─ M3–Mandol adapter → Mandol search representations
    → One retrieval request, without an LLM controller loop
    → Ranked evidence

Compression is optional, not a mandatory stage that every clip or query must pass through. Native and Mandol retrieval are alternative backends, not two consecutive searches.

Memory construction

The construction pipeline consumes a clip and its associated audio and produces four logical kinds of nodes:

Memory component

Role

Episodic nodes

Clip-grounded events, actions, and observations.

Semantic nodes

Extracted facts and semantic descriptions.

Voice nodes

Speaker-related audio evidence or features.

Face nodes

Visual identity evidence or features.

Two additional structures organize the memory. Character mappings associate face/voice evidence with character identifiers. Temporal indexes support access by clip and time. These are auxiliary structures, not additional text-memory node types.

The existence of a character identifier does not establish that every observation of the same real person has already been merged. Persistent identity consolidation remains ongoing work.

Callable memory compression

The StreamMCCO-derived compression algorithm is exposed as a callable operation over existing memory. It can be invoked separately from normal construction and retrieval.

At the architecture level, retrieval may consume either the raw memory or an output of the compression operation. Any derived retrieval representation must correspond to the memory version being searched. The diagram’s memory view is a logical description of this choice, not a claim that a particular selector class already exists.

The exact compression scope, mutation behavior, scheduling, and return type require source-level confirmation. This documentation does not assume that all four node modalities are compressed in the same way.

Retrieval path 1: native M3

User query → query encoding → native memory retrieval → ranked evidence

The application makes one retrieval call, with no LLM controller call to choose successive searches, inspect intermediate results, or reformulate the query.

“One retrieval call” describes the application-level retrieval contract. It does not prohibit internal encoding, ranking, metadata lookups, or evidence assembly. Any downstream answer-generation model is separate from retrieval.

Retrieval path 2: Mandol through an adapter

The adapter translates M3’s memory organization into Mandol-compatible representations without making Mandol a prerequisite for the native path.

M3 source

Mandol-side representation

Episodic memory

Memory units, grouped into clip-based spaces.

Semantic memory

Hierarchical-memory-like representation.

Character mappings

Entity representation.

The current description specifies grouping by clip. It does not establish an additional fixed-size parent grouping or exact hierarchical levels.

Mandol’s retrieval stack is used after adaptation:

                          ┌─ BM25 lexical search ────┐
Query → tokenize / encode ├─ 1024-D dense search ───┼→ candidate fusion
                          └─ Sparse-vector search ───┘       → reranker
                                                            → ranked evidence

BM25, dense search, and sparse search are parallel candidate sources—not a serial BM25 → dense → sparse pipeline. The 1024-dimensional setting describes the dense representation, not the sparse one. Encoding prepares representations before retrieval; it is not a final stage after reranking.

The adapter and memory-side representations are prepared during ingestion or refresh, rather than being conceptually rebuilt from the full graph for every query. The exact scheduling and cache implementation need code verification.

What is available, and what is still being developed?

Component

Status in this documentation

Clip/audio construction of multimodal memory

Present, as reported by the maintainer.

Character mappings and temporal indexes

Present, as reported by the maintainer.

Callable StreamMCCO compression

Present, as reported by the maintainer.

Native single-shot retrieval without a controller

Present, as reported by the maintainer.

M3–Mandol adapter and hybrid retrieval path

Present, as reported by the maintainer.

Persistent character/entity consolidation

In progress.

Consolidation concerns who an observation belongs to across clips and time. Compression concerns the representation and redundancy of stored memory. These are different operations; compression should not be presented as having solved fragmented person identity.

Dependencies and boundaries

Both retrieval paths depend on the M3 memory and the representations required by their own search stack. The native path does not require the Mandol adapter. The Mandol path requires the adapter, lexical/dense/sparse search representations, query preparation, candidate fusion, and a reranker. StreamMCCO is required only when compression is invoked. Consolidation is not a completed prerequisite for either existing retrieval path.

Concrete embedding and reranker models, local-versus-cloud execution, vector storage, package versions, and launch commands must be documented from the implementation. No particular vector database, GPU configuration, or external service is implied here.

See ARCHITECTURE.md for data flow, representation mappings, dependency contracts, and the consolidation boundary.