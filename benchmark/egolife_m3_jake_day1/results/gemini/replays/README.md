# Gemini — memory replays

Cumulative constructed memories at 20, 40 and 60 minutes after DAY1 11:09:42.08. These are historical saved graphs, including historical voice-node contents.

Each checkpoint ends 12.08 seconds before the requested cutoff because memory is committed by segment. The segment crossing the cutoff is excluded.

| Replay | Actual elapsed coverage | Last segment | Total nodes | Voice identities | Face identities |
| --- | --- | --- | --- | --- | --- |
| [20 minutes](memories_20min.md) | 00:19:47.92 | 41 | 489 | 106 | 0 |
| [40 minutes](memories_40min.md) | 00:39:47.92 | 83 | 964 | 190 | 0 |
| [60 minutes](memories_60min.md) | 00:59:47.92 | 126 | 1488 | 297 | 0 |

[Selection provenance and source hashes](../../../provenance/replays/gemini.json).

Regenerate with `python3 scripts/replay_gemini_memories.py` from the experiment folder.
