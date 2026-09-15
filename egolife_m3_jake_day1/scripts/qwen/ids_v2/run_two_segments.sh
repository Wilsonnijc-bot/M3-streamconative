#!/usr/bin/env bash
source /opt/streammeco/run/egolife_10q_qwen35_4b_fps2_thinking_ids_v2/environment.sh
exec 9>"$RUN/launch.lock"
flock -n 9 || exit 20
exec > >(tee -a "$RUN/pipeline.log") 2>&1
server_pid=''
finish() {
 rc=$?
 trap - EXIT
 if [ -n "$server_pid" ]; then kill "$server_pid" 2>/dev/null || true; fi
 printf 'exit_status=%s\nfinished_at=%s\n' "$rc" "$(date -Is)" > "$RUN/launcher_status.txt"
 exit "$rc"
}
trap finish EXIT
[ "$(tmux display-message -p '#S')" = egolife_10q_qwen ] || exit 22
printf 'state=two_segment_test\nstarted_at=%s\n' "$(date -Is)" > "$RUN/launcher_status.txt"
python "$RUN/reuse_artifacts.py"
python -m compileall -q benchmarks/qwen_runtime.py benchmarks/qwen_multimodal_server.py mmagent/memory_processing_local_qwen.py mmagent/qwen_memory_prompt.py
sha256sum mmagent/prompts.py mmagent/memory_processing_local_qwen.py mmagent/qwen_memory_prompt.py benchmarks/qwen_runtime.py benchmarks/qwen_multimodal_server.py "$RUN/run_two_segments.sh" > "$RUN/code_hashes.sha256"
python - <<'PY'
from mmagent.qwen_memory_prompt import IDENTITY_SYSTEM_PROMPT
from pathlib import Path
import os
Path(os.environ['QWEN_RUN'],'qwen_identity_system_prompt.md').write_text('# Qwen-only identity system prompt v2\n\n'+IDENTITY_SYSTEM_PROMPT+'\n')
PY
PYTHONPATH="$RUN/test_deps:$PYTHONPATH" python -m pytest tests/test_qwen_runtime.py tests/test_asr_resilience.py tests/test_pipeline_optimizations.py tests/test_segment_resilience.py tests/test_warm_query.py tests/test_export_mandol.py -q > "$RUN/tests.log" 2>&1
python benchmarks/qwen_multimodal_server.py > "$RUN/server.log" 2>&1 &
server_pid=$!
python - <<'PY'
import httpx,time
for i in range(180):
 try:
  r=httpx.get('http://127.0.0.1:8766/health');r.raise_for_status();assert r.json()['model']=='Qwen/Qwen3.5-4B';break
 except httpx.HTTPError:time.sleep(2)
else:raise RuntimeError('Qwen server failed to start')
PY
python benchmarks/egolife_first10.py build --qa "$QA" --clips "$CLIPS" --results "$RESULTS" --work "$WORK" --max-segments 2
python "$RUN/validate_identity.py"
sha256sum -c /opt/streammeco/run/egolife_10q_qwen35_4b_fps2_thinking/gemini_prompt_before_ids_patch.sha256 > "$RUN/gemini_prompt_unchanged.txt"
echo TWO_SEGMENT_IDENTITY_TEST_COMPLETE
