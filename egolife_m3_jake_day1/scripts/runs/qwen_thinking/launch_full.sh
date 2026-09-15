#!/usr/bin/env bash
source /opt/streammeco/run/egolife_10q_qwen35_4b_fps2_thinking_ids_v2_full/environment.sh
exec 8>"$RUN/launch.lock"
flock -n 8 || exit 20
exec > >(tee -a "$RUN/launcher.log") 2>&1
server_pid=''
finish() {
 rc=$?; trap - EXIT
 if [ -n "$server_pid" ]; then kill "$server_pid" 2>/dev/null || true; fi
 printf 'exit_status=%s\nfinished_at=%s\n' "$rc" "$(date -Is)" > "$RUN/launcher_status.txt"
 if [ "$rc" -ne 0 ]; then printf 'exit_status=%s\nfinished_at=%s\n' "$rc" "$(date -Is)" > "$RUN/pipeline_status.txt"; fi
 exit "$rc"
}
trap finish EXIT
[ "$(tmux display-message -p '#S')" = egolife_10q_qwen ] || exit 22
printf 'exit_status=running\nphase=startup\nstarted_at=%s\n' "$(date -Is)" > "$RUN/pipeline_status.txt"
printf 'exit_status=running\nstarted_at=%s\n' "$(date -Is)" > "$RUN/launcher_status.txt"
python "$RUN/verify_resume.py"
PYTHONPATH="$RUN/test_deps:$PYTHONPATH" python -m pytest tests/test_qwen_runtime.py tests/test_asr_resilience.py tests/test_pipeline_optimizations.py tests/test_segment_resilience.py tests/test_warm_query.py tests/test_export_mandol.py -q > "$RUN/tests.log" 2>&1
python benchmarks/qwen_multimodal_server.py > "$RUN/server.log" 2>&1 &
server_pid=$!
python - <<'PY'
import httpx,time
for i in range(180):
 try:
  r=httpx.get('http://127.0.0.1:8766/health');r.raise_for_status();assert r.json()['model']=='Qwen/Qwen3.5-4B';break
 except httpx.HTTPError:time.sleep(2)
else:raise RuntimeError('Qwen server startup failed')
PY
bash "$RUN/run_pipeline.sh"
