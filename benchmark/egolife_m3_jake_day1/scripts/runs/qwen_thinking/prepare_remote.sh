#!/usr/bin/env bash
set -Eeuo pipefail
SOURCE=/opt/streammeco/run/egolife_10q_qwen35_4b_fps2_thinking_ids_v2
RUN=/opt/streammeco/run/egolife_10q_qwen35_4b_fps2_thinking_ids_v2_full
[ ! -e "$RUN/work/build_state.pkl" ] || { echo 'Already prepared; refusing overwrite'; exit 1; }
mkdir -p "$RUN/lineage"
cp -a "$SOURCE/code" "$SOURCE/work" "$SOURCE/results" "$RUN/"
ln -s /opt/streammeco/run/egolife_10q_qwen35_4b_fps2/test_deps "$RUN/test_deps"
cp "$SOURCE/server_calls.jsonl" "$RUN/server_calls.jsonl"
cp "$SOURCE/server_model_manifest.json" "$SOURCE/launcher_status.txt" "$SOURCE/code_hashes.sha256" "$SOURCE/checkpoint_hashes.sha256" "$SOURCE/gemini_prompt_unchanged.txt" "$RUN/lineage/"
cp "$SOURCE/qwen_identity_system_prompt.md" "$RUN/"
cp /opt/streammeco/run/egolife_10q_qwen35_4b_fps2_thinking/gemini_prompt_before_ids_patch.sha256 "$RUN/lineage/"
sha256sum -c "$RUN/lineage/gemini_prompt_before_ids_patch.sha256" > "$RUN/gemini_prompt_unchanged.txt"
exec bash "$RUN/launch_full.sh"
