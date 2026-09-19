# M3 → Mandol Adapter Plan

## 1. Target architecture

```text
Video / Audio
     ↓
M3-Agent memorization
     ↓
M3 VideoGraph
     ↓
[optional StreamMeCo compression]
     ↓
M3 → Mandol Adapter
     │
     ├── episodic nodes ───────────────┐
     ├── semantic nodes ───────────────┤
     ├── face/voice → entity registry  │
     └── LLM entity-relation builder ──┤
                                       ↓
                              Mandol SemanticGraph
                                       │
                          shared FAISS/BM25/SPLADE
                                       │
                                       ↓
                              Mandol retrieval
                                       │
                                       ↓
                              one answer LLM
```

M3 remains responsible for multimodal understanding. StreamMeCo remains an optional preprocessing step over the M3 graph. Mandol becomes the serving/retrieval representation. M3 itself already separates memorization from its iterative control loop, so replacing the control side is a clean boundary.

---

# 2. Exact MemorySpace hierarchy

Assuming M3's normal **30-second clips**, group five adjacent clips into one 150-second parent space.

```text
video_001
│
├── block_000                    # clips 0–4
│   ├── clip_000
│   ├── clip_001
│   ├── clip_002
│   ├── clip_003
│   └── clip_004
│
├── block_001                    # clips 5–9
│   ├── clip_005
│   ├── clip_006
│   ├── clip_007
│   ├── clip_008
│   └── clip_009
│
└── ...
```

Mandol's current representation supports tree-shaped `MemorySpace`s while its FAISS/index structures remain global, so spaces are logical membership/filtering structures rather than independent vector databases.

### Important simplification

Do **not** create:

```text
clip_001_episodic
clip_001_semantic
clip_001_entity_relation

clip_002_episodic
clip_002_semantic
clip_002_entity_relation
...
```

Instead:

```text
clip_001
├── E001  [type=episodic]
├── E002  [type=episodic]
├── S001  [type=semantic]
├── R001  [type=entity_relation]
└── R002  [type=entity_relation]
```

The unit's `memory_type` tells us what it is.

This substantially reduces MemorySpace count.

---

# 3. Membership rule

Every searchable unit gets **three kinds of membership**.

For example:

```text
E128
│
├── temporal membership
│      ├── clip_038
│      └── block_007
│
└── type membership
       └── episodic
```

Therefore:

```yaml
unit: E128

spaces:
  - video_001/block_007
  - video_001/block_007/clip_038
  - episodic
```

Likewise:

```yaml
unit: S055
spaces:
  - video_001/block_007
  - video_001/block_007/clip_038
  - semantic
```

and:

```yaml
unit: R031
spaces:
  - video_001/block_007
  - video_001/block_007/clip_038
  - entity_relation
```

This is deliberate.

Even though the spaces are hierarchical, **the adapter explicitly inserts each UID into both the clip and 5-clip block**.

Therefore searching `block_007` directly searches all relevant units without requiring recursive child traversal.

---

# 4. What becomes a MemoryUnit

Not every M3 node should become a Mandol unit.

### Convert directly

```text
M3 episodic node
      ↓
Mandol MemoryUnit(type=episodic)

M3 semantic node
      ↓
Mandol MemoryUnit(type=semantic)
```

### Do not directly index

```text
M3 face node
M3 voice node
```

Those instead feed an **entity registry**.

### Create through adapter

```text
M3 face/voice/entity information
+
episodic/semantic text
      ↓
entity-relation LLM
      ↓
Mandol MemoryUnit(type=entity_relation)
```

So Mandol ultimately searches three memory types:

```text
episodic
semantic
entity_relation
```

---

# 5. Exact MemoryUnit schema

Use one common schema for every searchable unit:

```yaml
uid: "video001:clip038:E128"

raw_data:
  text_content: "Character_0 picked up the red cup."

metadata:
  video_id: "video001"

  block_id: 7
  clip_id: 38

  start_sec: 1140
  end_sec: 1170

  memory_type: "episodic"

  entity_ids:
    - "character_0"
    - "red_cup"

  provenance:
    m3_node_ids:
      - 128
```

Semantic example:

```yaml
uid: "video001:clip038:S055"

raw_data:
  text_content: "The red cup belongs to Character_0."

metadata:
  memory_type: "semantic"
  block_id: 7
  clip_id: 38
  entity_ids:
    - "character_0"
    - "red_cup"

  provenance:
    m3_node_ids:
      - 251
```

---

# 6. Entity registry: use M3 rather than rediscovering people

M3 already contains face/voice information and entity-centric multimodal associations.

The adapter should first construct:

```python
EntityRegistry = {
    "character_0": {
        "face_nodes": [...],
        "voice_nodes": [...],
    },

    "character_1": {
        "face_nodes": [...],
        "voice_nodes": [...],
    }
}
```

Conceptually:

```text
face_13 ───┐
face_29 ───┼──► character_0
voice_04 ──┘
```

The relation-building LLM must **not** decide whether these represent the same person.

M3 already solved that upstream.

---

# 7. Adapt Mandol's entity-relation builder

Mandol already exposes high-level construction for entity-relation structures.

Instead of using it exactly as designed for conversations, wrap it with an M3-specific input stage.

For each clip:

```text
M3 entities
     +
M3 episodic memories
     +
M3 semantic memories
     ↓
relation extraction LLM
```

Example input:

```text
CLIP 38

Known person entities:
- character_0
- character_1

Episodic:
1. Character_0 entered the kitchen.
2. Character_1 handed Character_0 a red cup.
3. Character_0 placed the cup beside the sink.

Semantic:
1. Character_1 is wearing a black shirt.
2. The sink is inside the kitchen.
```

Desired structured output:

```json
{
  "entities": [
    {"id": "character_0", "type": "person"},
    {"id": "character_1", "type": "person"},
    {"id": "red_cup", "type": "object"},
    {"id": "sink", "type": "object"},
    {"id": "kitchen", "type": "place"}
  ],
  "relations": [
    {
      "subject": "character_1",
      "predicate": "gives",
      "object": "red_cup",
      "target": "character_0",
      "evidence": ["E2"]
    },
    {
      "subject": "character_0",
      "predicate": "places_near",
      "object": "red_cup",
      "target": "sink",
      "evidence": ["E3"]
    },
    {
      "subject": "sink",
      "predicate": "located_in",
      "object": "kitchen",
      "evidence": ["S2"]
    }
  ]
}
```

---

# 8. Person entities vs other entities

Use two different policies.

### Person entities

Canonical IDs come directly from M3:

```text
character_0
character_1
...
```

The LLM cannot rename or merge them.

### Objects / places / other entities

The relation LLM can generate:

```text
red_cup
sink
kitchen
blue_jacket
laptop
...
```

The adapter performs basic normalization:

```text
"red cup" → red_cup
"the red cup" → red_cup
```

V1 should use conservative string normalization only.

Do **not** add another expensive LLM deduplication round yet.

---

# 9. Relation becomes both graph edge and searchable MemoryUnit

This is important.

Suppose the relation is:

```text
character_1 --gives--> red_cup --to--> character_0
```

Store it in **two forms**.

### A. Structured SemanticGraph relation

```text
character_1
      │ gives
      ▼
   red_cup

red_cup
      │ given_to
      ▼
character_0
```

Mandol's `SemanticGraph` natively supports explicit relationships.

### B. Searchable relation MemoryUnit

```yaml
uid: "video001:clip038:R003"

raw_data:
  text_content:
    "Character_1 gave the red cup to Character_0."

metadata:
  memory_type: "entity_relation"

  subject: "character_1"
  predicate: "gives"
  object: "red_cup"
  target: "character_0"

  block_id: 7
  clip_id: 38

  evidence_uids:
    - "video001:clip038:E002"
```

Why both?

Because the textual unit participates naturally in:

```text
BM25
SPLADE
dense similarity
```

while the structured representation enables:

```text
graph expansion
entity traversal
relation reasoning
```

Mandol's retrieval layer supports both multi-method text retrieval and graph expansion.

---

# 10. Exact adapter procedure

For each finalized M3 graph:

```python
adapt(video_graph):
```

execute:

```text
STEP 1
Read M3 graph
    ↓

STEP 2
Resolve canonical M3 person entities
face + voice
    ↓
EntityRegistry
    ↓

STEP 3
Iterate clips in temporal order
    ↓

STEP 4
For each clip:
    create/get clip MemorySpace
    create/get its 5-clip parent MemorySpace
    ↓

STEP 5
Convert retained M3 episodic nodes
    → episodic MemoryUnits
    ↓

STEP 6
Convert retained M3 semantic nodes
    → semantic MemoryUnits
    ↓

STEP 7
Collect:
    episodic text
    semantic text
    canonical entities
    ↓

STEP 8
ONE entity-relation LLM call for this clip
    ↓
validated entities + relations
    ↓

STEP 9
Create:
    relation MemoryUnits
    explicit SemanticGraph edges
    ↓

STEP 10
Insert units into Mandol
    ↓
shared dense/BM25/SPLADE indexes
```

The entity-relation LLM runs during **memory construction**, not retrieval.

Therefore it does not affect retrieval latency.

---

# 11. Five-clip block calculation

Make block membership deterministic:

```python
BLOCK_SIZE = 5

block_id = clip_id // BLOCK_SIZE
```

Examples:

```text
clip 0 → block 0
clip 1 → block 0
clip 2 → block 0
clip 3 → block 0
clip 4 → block 0

clip 5 → block 1
clip 6 → block 1
...
```

For 30-second M3 clips:

```text
clip space  = ~30 sec
block space = ~150 sec
```

No LLM decides boundaries in V1.

That makes construction deterministic and cheap.

---

# 12. Resulting graph

Example after processing clips 35–39:

```text
BLOCK_007
│
├── CLIP_035
│   ├── E101
│   ├── E102
│   ├── S041
│   └── R020
│
├── CLIP_036
│   ├── E103
│   ├── S042
│   └── R021
│
├── CLIP_037
│   ├── E104
│   ├── E105
│   └── R022
│
├── CLIP_038
│   ├── E106
│   ├── S043
│   ├── R023
│   └── R024
│
└── CLIP_039
    ├── E107
    ├── S044
    └── R025
```

Globally:

```text
character_0
   ▲     ▲       ▲
   │     │       │
 R020  E104    R024
   │     │       │
clip35 clip37  clip38
```

So:

**temporal organization is local**

while:

**entities are global**.

---

# 13. StreamMeCo position

Use:

```text
M3
 ↓
full VideoGraph
 ↓
StreamMeCo
 ↓
compressed VideoGraph
 ↓
Adapter
 ↓
Mandol
```

StreamMeCo explicitly operates on M3 memory graphs and produces compressed graphs for subsequent inference.

The reason for adapting **after** compression is important:

```text
M3 generates 100 memories
        ↓
StreamMeCo retains 65
        ↓
Adapter builds Mandol from those 65
```

Then relation extraction is based on the memory that actually survives into the serving system.

You avoid creating entity relations whose supporting M3 memories were subsequently deleted.

---

# 14. Retrieval — no router

There is **no query router**.

Mandol maintains its shared indexes globally. Current Mandol uses a global FAISS index with MemorySpace-filtered retrieval, plus BM25/SPLADE integration.

Normal query:

```text
query
   ↓
Mandol smart_search
   ↓
BM25
+
dense
+
SPLADE
+
optional graph expansion
   ↓
fusion
   ↓
reranker
   ↓
Top-K
```

Search all three types:

```text
episodic
semantic
entity_relation
```

in the same retrieval pass / shared index.

There is no:

```text
LLM → decide episodic vs semantic vs relation
```

and no:

```text
search clip1
search clip2
search clip3
...
```

---

# 15. Then what are the clip/block spaces for?

They give us **retrieval scope when useful**, rather than becoming the normal search algorithm.

### General question

```text
"What cup did Character_0 use?"
```

Search:

```text
whole video / all memories
```

### Already-known temporal region

```text
"What happened around 20 minutes?"
```

Convert the timestamp to:

```text
block_008
```

and search only that MemorySpace.

### Follow-up after retrieving clip 42

If the answer requires more local context:

```text
clip_42
      ↓
parent block_08
      ↓
search neighboring five clips
```

This can be done algorithmically without an LLM router.

---

# 16. V1 should NOT create block summaries

For now:

```text
block_007
```

should only be a **container/index scope** over five clips.

Do not yet spend another LLM call producing:

```text
"Summary of clips 35–39..."
```

That is a V2 experiment.

V1 should isolate whether the structural hierarchy itself improves retrieval.

Later we can test:

```text
block MemorySpace
+
one block summary MemoryUnit
```

for coarse-to-fine retrieval.

---

# 17. Concrete implementation modules

```text
m3_mandol_adapter/
│
├── adapter.py
├── entity_registry.py
├── relation_builder.py
├── space_builder.py
├── validators.py
└── index_builder.py
```

### `entity_registry.py`

```python
build_entity_registry(video_graph)
```

Output:

```python
Dict[canonical_entity_id, EntityRecord]
```

---

### `space_builder.py`

```python
get_block_space(video_id, clip_id)
get_clip_space(video_id, clip_id)
```

Uses:

```python
block_id = clip_id // 5
```

---

### `adapter.py`

```python
convert_episodic_node(...)
convert_semantic_node(...)
```

No LLM.

Pure deterministic transformation.

---

### `relation_builder.py`

```python
extract_relations(
    entities,
    episodic_memories,
    semantic_memories,
)
```

Exactly **one LLM call per clip**.

---

### `validators.py`

Reject:

```text
unknown Character IDs
missing evidence
malformed relations
relations referencing nonexistent memories
```

---

### `index_builder.py`

Insert:

```text
MemoryUnits
MemorySpace memberships
SemanticGraph relationships
```

and build Mandol indexes.

---

# 18. Final invariant

After adaptation, every searchable memory should satisfy:

```text
MemoryUnit
   │
   ├── belongs to exactly one clip
   │
   ├── belongs to exactly one 5-clip block
   │
   ├── has exactly one memory_type
   │      episodic
   │      semantic
   │      entity_relation
   │
   ├── has explicit M3 provenance
   │
   └── references global canonical entities
```

The structure therefore becomes:

```text
                     VIDEO
                       │
        ┌──────────────┴──────────────┐
        ▼                             ▼
     BLOCK 0                       BLOCK 1
     5 clips                       5 clips
        │                             │
  ┌─────┼─────┐                 ┌─────┼─────┐
  ▼     ▼     ▼                 ▼     ▼     ▼
clip0 clip1 ... clip4          clip5 clip6 ... clip9
  │
  ├─ episodic MemoryUnits
  ├─ semantic MemoryUnits
  └─ entity-relation MemoryUnits

                GLOBAL ENTITY GRAPH
                ▲       ▲       ▲
                │       │       │
        character_0   cup   kitchen
```

## Final design

**M3 node → searchable `MemoryUnit` only for episodic/semantic memories.**

**M3 face/voice nodes → canonical global entity registry.**

**Mandol-style LLM construction → entity-relation MemoryUnits + graph edges, once per clip.**

**1 clip → child `MemorySpace`.**

**5 clips → parent `MemorySpace`.**

**Each unit belongs directly to its clip, its 5-clip block, and its memory-type space.**

**All embeddings/BM25/SPLADE remain in Mandol's shared indexes.**

**Retrieval does not iterate over MemorySpaces and does not use an LLM router.**

**MemorySpaces provide hierarchy/filtering; Mandol's global indexes provide speed.**
