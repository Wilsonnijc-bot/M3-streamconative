# Bedroom first-segment functional preflight — retrieved memories

## Results overview

Correctness below is separate Gemini judging against the supplied references, not an official benchmark score or a direct retrieval precision/recall measurement.

| Method | Correct / answered | Retrieval rounds | Empty rounds | Evidence per nonempty round |
| --- | --- | --- | --- | --- |
| A | 0/1 | 1 | 0 | 9 |
| B | 0/1 | 1 | 0 | 9 |
| C | 0/1 | 1 | 0 | 7 |
| D | 0/1 | 1 | 0 | 2 |

A uses iterative controller searches; B uses uncompressed one-shot retrieval; C uses compressed one-shot retrieval; D uses Mandol hybrid retrieval and reranking. D returned 2 evidence nodes per question, versus 20 per nonempty A/B/C round, so evidence budgets are unequal.

### Per-question model judgments

| Question | A | B | C | D |
| --- | --- | --- | --- | --- |
| 1 | Pending | Pending | Pending | Pending |

[Stage-by-stage latency, including mean and median](latency.md).

## Q1 · Method A

What activity is visible in the observed scene?

Answer: **A young woman enters a bedroom, takes off her outdoor winter jacket and baseball cap, hangs them on a coat rack, and places her backpack on the bed.**; reference: **Functional check only; not benchmark scoring**. Retrieval requests: 1.

**Memory cutoff:** 30.0 seconds.

### Retrieval 1

**Query:** main activity actions observed scene

- **Node 9**: <voice_0> belongs to the young woman as she walks through the apartment.
- **Node 7**: Slings the backpack over her shoulder, she turns and walks out of the bedroom into the living area.
- **Node 6**: She turns around, adjusts her hair, and picks up her backpack and phone from the bed.
- **Node 8**: The woman is arriving indoors and shedding her outdoor winter layers to get comfortable.
- **Node 1**: A young woman wearing a black winter jacket and a black baseball cap walks into a bedroom from the hallway.
- **Node 4**: She hangs the black jacket onto the coat rack near the window.
- **Node 3**: She takes off her heavy black jacket, revealing a white long-sleeved top.
- **Node 5**: She removes her black baseball cap and hangs it on the coat rack as well.
- **Node 2**: She sets her brown backpack down on the bed.

## Q1 · Method B

What activity is visible in the observed scene?

Answer: **A young woman arriving indoors, walking through her apartment, and shedding her outdoor winter layers (removing and hanging up her black jacket and cap, and handling her backpack).**; reference: **Functional check only; not benchmark scoring**. Retrieval requests: 1.

**Memory cutoff:** 30.0 seconds.

### Retrieval 1

**Query:** What activity is visible in the observed scene?

- **Node 9**: <voice_0> belongs to the young woman as she walks through the apartment.
- **Node 7**: Slings the backpack over her shoulder, she turns and walks out of the bedroom into the living area.
- **Node 8**: The woman is arriving indoors and shedding her outdoor winter layers to get comfortable.
- **Node 3**: She takes off her heavy black jacket, revealing a white long-sleeved top.
- **Node 4**: She hangs the black jacket onto the coat rack near the window.
- **Node 1**: A young woman wearing a black winter jacket and a black baseball cap walks into a bedroom from the hallway.
- **Node 6**: She turns around, adjusts her hair, and picks up her backpack and phone from the bed.
- **Node 5**: She removes her black baseball cap and hangs it on the coat rack as well.
- **Node 2**: She sets her brown backpack down on the bed.

## Q1 · Method C

What activity is visible in the observed scene?

Answer: **A young woman is arriving indoors, walking through an apartment, and shedding her outdoor winter layers (removing her jacket and baseball cap, and setting down her backpack).**; reference: **Functional check only; not benchmark scoring**. Retrieval requests: 1.

**Memory cutoff:** 30.0 seconds.

### Retrieval 1

**Query:** What activity is visible in the observed scene?

- **Node 9**: <voice_0> belongs to the young woman as she walks through the apartment.
- **Node 7**: Slings the backpack over her shoulder, she turns and walks out of the bedroom into the living area.
- **Node 8**: The woman is arriving indoors and shedding her outdoor winter layers to get comfortable.
- **Node 3**: She takes off her heavy black jacket, revealing a white long-sleeved top.
- **Node 1**: A young woman wearing a black winter jacket and a black baseball cap walks into a bedroom from the hallway.
- **Node 5**: She removes her black baseball cap and hangs it on the coat rack as well.
- **Node 2**: She sets her brown backpack down on the bed.

## Q1 · Method D

What activity is visible in the observed scene?

Answer: **A young woman is walking through the apartment and entering a bedroom from the hallway.**; reference: **Functional check only; not benchmark scoring**. Retrieval requests: 1.

**Memory cutoff:** 30.0 seconds.

### Retrieval 1

**Query:** What activity is visible in the observed scene?

- **Node m3:bedroom-01-q01:clip:1:semantic:9** → M3 9: <voice_0> belongs to the young woman as she walks through the apartment.
- **Node m3:bedroom-01-q01:clip:1:episodic:1** → M3 1: A young woman wearing a black winter jacket and a black baseball cap walks into a bedroom from the hallway.
