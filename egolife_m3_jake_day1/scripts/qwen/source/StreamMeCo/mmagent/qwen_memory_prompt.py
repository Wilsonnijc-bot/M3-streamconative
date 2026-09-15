"""Qwen-only addition; the shared Gemini memory prompt is left unchanged."""
IDENTITY_SYSTEM_PROMPT = """Preserve speaker identity when constructing memory from the supplied character features.

- Voice features map exact IDs such as <voice_0> to timestamped transcripts. These IDs already identify the speakers; they remain usable even when no face features are supplied or the visible speaker cannot be identified.
- For every supplied voice ID with nonempty speech, include at least one episodic memory that quotes or faithfully summarizes that speaker's transcript, using the exact ID as the speaker. Preserve distinct substantive utterances as separate atomic memories. Do not replace the ID with 'a speaker', 'the voice track', or an inferred visual role.
- When a semantic conclusion concerns a known speaker, retain that speaker's exact voice ID. Use only IDs supplied in the input; do not copy example IDs from instructions.
- A voice ID does not establish which visible person is speaking. Do not assign it to the camera wearer or another visible person, or assert face/voice equivalence, without supporting evidence. If no face IDs are supplied, do not invent any.
- Keep dialogue grounded in the provided transcript. Do not substitute a plausible scene description for what the speaker actually said.

Keep the existing video_description/high_level_conclusions JSON schema and all other task instructions unchanged."""
