# Qwen memories — speaker-identity prompt refinement

**Jake DAY1 · first two segments · Qwen3.5-4B · thinking on · 2 FPS**

These are the model-generated memories committed to a fresh M3 graph. The wording is preserved; speaker IDs are displayed as inline code for readability. No IDs were inserted into the generated memories by postprocessing.

**14 episodic memories and 6 semantic conclusions.** Identity-reference validation: **failed**.

| Segment | Supplied voice IDs | IDs retained in episodic memory | New speaker-memory edges | Frames | Generation |
| --- | --- | --- | ---: | ---: | ---: |
| 1 | `<voice_0>`, `<voice_1>` | `<voice_0>`, `<voice_1>` | 5 | 36 | 151.4 s |
| 2 | `<voice_0>` |  | 1 | 60 | 138.3 s |

## Segment 1

Source: `DAY1_A1_JAKE_11094208.mp4`.

### Episodic memories

1. The camera wearer holds a smartphone displaying a white screen while observing a group of people seated around a table.
2. At timestamp 00:04, `<voice_0>` announces, 'Good, then a stopwatch.'
3. The group remains seated at the table with various items spread across the surface.
4. At timestamp 00:12, `<voice_1>` states, 'Time ding.'
5. At timestamp 00:13, `<voice_0>` confirms, 'Yes, ding once.'
6. The camera wearer manipulates the smartphone screen, revealing a countdown timer.
7. The timer progresses from approximately 23 minutes down to zero.
8. The camera wearer places a hand on a black case resting on the table near the end of the sequence.

### Semantic conclusions

1. The participants appear to be engaging in a timed activity or challenge facilitated by the smartphone.
2. Speaker MAI (`<voice_0>`, `<voice_1>`) is responsible for initiating and signaling the timing mechanism.
3. No facial features are provided to visually identify the speaker MAI among the group members.

[Construction audit](results/clip_audits/clip_1_audit.json) · [Committed graph](results/clip_audits/clip_1_graph.json)

## Segment 2

Source: `DAY1_A1_JAKE_11100000.mp4`.

### Episodic memories

1. A group of five individuals sits around a rectangular table covered with a red and white checkered cloth.
2. The camera wearer distributes black carrying cases to the participants seated at the table.
3. Each participant places the contents of the case, which appear to be earplugs, into their ears.
4. The camera wearer confirms that all group members have successfully put on the earplugs.
5. The camera wearer holds up a smartphone displaying a digital timer set to zero.
6. The group discusses their plans for the final day of their current activity.

### Semantic conclusions

1. The group is preparing for a discussion session scheduled for their last day.
2. Participants utilize earplugs to manage auditory environment before the discussion begins.
3. The speaker identified as `<voice_0>` coordinates the distribution of equipment and initiates the session.

[Construction audit](results/clip_audits/clip_2_audit.json) · [Committed graph](results/clip_audits/clip_2_graph.json)

## Review outcome

**Partial improvement; not accepted as a reliable fix.**

- Segment 1 includes both supplied speaker IDs; segment 2 still omits its speaker ID from episodic dialogue.
- Qwen incorrectly treats the ASR provider label “MAI” as a person’s name, grouping two voice IDs under it.
- The input “时间戳” means “timestamp”; the generated “Time ding” is a mistranslation.
- Both generations completed at 2 FPS with thinking on and no truncation. The test exited with status 1 because the identity-coverage check failed, not because of an inference crash.

[Supplied transcript excerpts](results/transcript_review_inputs.json) · [Review record](results/manual_identity_review.json)

## What changed

Only the isolated Qwen memory path received an additional system message: retain supplied speaker IDs, summarize each speaker’s actual transcript, and avoid guessing voice-to-face identities. The shared base prompt and Gemini memory prompt were left unchanged. Thinking, 2-FPS sampling, the 16,384-token budget and decoding settings were retained.

[Exact Qwen-only system prompt](qwen_identity_system_prompt.md) · [Identity validation](results/identity_validation.json) · [Gemini prompt hash verification](gemini_prompt_unchanged.txt)

Generation times are CUDA-synchronized and include thinking. Gemini was running concurrently. Passing this two-segment identity test does not establish accuracy across the full benchmark.
