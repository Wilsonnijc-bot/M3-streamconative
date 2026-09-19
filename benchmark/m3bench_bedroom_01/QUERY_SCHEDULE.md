# Query schedule

Each method retrieves against an immutable memory snapshot containing only observations up to the effective cutoff. Evaluation can execute later; it cannot see later memory.

| Question | Requested | Effective cutoff |
| --- | --- | --- |
| Q09 | 01:42 | 01:30 |
| Q01 | 07:20 | 07:20 |
| Q08 | 07:20 | 07:20 |
| Q10 | 11:45 | 11:45 |
| Q11 | 21:05 | 21:05 |
| Q02 | 36:03 | 36:03 |
| Q03 | 36:03 | 36:03 |
| Q04 | 36:03 | 36:03 |
| Q05 | 36:03 | 36:03 |
| Q06 | 36:03 | 36:03 |
| Q07 | 36:03 | 36:03 |
| Q12 | 36:03 | 36:03 |
| Q13 | 36:03 | 36:03 |
| Q14 | 36:03 | 36:03 |
| Q15 | 36:03 | 36:03 |

Q09 uses the saved 01:30 graph, 12 seconds early, to preserve existing construction without including future observations. All other cutoffs match the requested timestamps. The final 0.264 seconds of the video are outside the 36:03 cutoff.

73 source clips become 76 processing segments because 07:20, 11:45 and 21:05 split existing 30-second clips. Q01 and Q08 share the same cutoff; the ten final questions share 36:03. All original question IDs are retained.
