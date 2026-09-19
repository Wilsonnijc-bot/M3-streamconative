#!/usr/bin/env bash
source /opt/streammeco/run/egolife_10q_qwen35_4b_fps2_thinking_ids_v2_full/environment.sh
exec 9>"$RUN/pipeline.lock"
flock -n 9 || { echo 'Duplicate pipeline refused'; exit 20; }
exec > >(tee -a "$RUN/pipeline.log") 2>&1
finish() {
 rc=$?
 trap - EXIT
 printf 'exit_status=%s\nfinished_at=%s\n' "$rc" "$(date -Is)" > "$RUN/pipeline_status.txt"
 printf '[%s] PIPELINE_EXIT_STATUS=%s\n' "$(date -Is)" "$rc"
 exit "$rc"
}
trap finish EXIT
[ -n "${TMUX:-}" ] || { echo 'Must run in egolife_10q_qwen tmux'; exit 21; }
[ "$(tmux display-message -p '#S')" = egolife_10q_qwen ] || exit 22
python "$RUN/verify_resume.py"
phase() {
 name=$1
 shift
 printf '[%s] PHASE_START %s\n' "$(date -Is)" "$name"
 "$@"
 printf '[%s] PHASE_COMPLETE %s\n' "$(date -Is)" "$name"
}
printf 'exit_status=running\nstarted_at=%s\n' "$(date -Is)" > "$RUN/pipeline_status.txt"
printf '[%s] PIPELINE_START model=Qwen/Qwen3.5-4B trials=40 session=egolife_10q_qwen\n' "$(date -Is)"
sha256sum benchmarks/qwen_multimodal_server.py "$RUN/environment.sh" "$RUN/launch_full.sh" mmagent/qwen_memory_prompt.py benchmarks/egolife_first10.py benchmarks/qwen_runtime.py benchmarks/qwen_report.py mmagent/memory_processing_local_qwen.py mmagent/utils/chat_api.py mmagent/utils/asr_resilience.py mmagent/voice_processing.py benchmarks/segment_resilience.py benchmarks/segment_prefetch.py cloud_http.py "$MANDOL/benchmarks/egolife_m3_first10.py" > "$RESULTS/code_hashes.sha256"
COMMON=(--qa "$QA" --results "$RESULTS" --work "$WORK")
phase memory_build python benchmarks/egolife_first10.py build --clips "$CLIPS" "${COMMON[@]}"
phase compression python benchmarks/egolife_first10.py compress "${COMMON[@]}"
phase mandol_export python benchmarks/egolife_first10.py export-mandol "${COMMON[@]}"
for method in A B C; do
 phase "eval_$method" python benchmarks/egolife_first10.py eval "${COMMON[@]}" --method "$method" --backend qwen
done
deactivate
cd "$MANDOL"
source /opt/streammeco/mandol-venv/bin/activate
phase mandol_adapt python benchmarks/egolife_m3_first10.py adapt --qa "$QA" --results "$RESULTS"
phase eval_D python benchmarks/egolife_m3_first10.py eval --qa "$QA" --results "$RESULTS" --backend qwen
deactivate
cd "$SMC"
source /opt/streammeco/.venv/bin/activate
phase report python benchmarks/egolife_first10.py report "${COMMON[@]}"
phase validate python benchmarks/egolife_first10.py validate "${COMMON[@]}"
printf '[%s] PIPELINE_COMPLETE\n' "$(date -Is)"
