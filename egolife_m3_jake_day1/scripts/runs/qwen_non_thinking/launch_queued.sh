#!/usr/bin/env bash
set -Eeuo pipefail
source /opt/streammeco/run/egolife_10q_qwen35_4b_fps2/environment.sh
exec 8>"$RUN/launch.lock"
flock -n 8 || exit 20
exec > >(tee -a "$RUN/queue.log") 2>&1
finish() { rc=$?; trap - EXIT; printf 'exit_status=%s\nfinished_at=%s\n' "$rc" "$(date -Is)" > "$RUN/launcher_status.txt"; exit "$rc"; }
trap finish EXIT
[ "$(tmux display-message -p '#S')" = egolife_10q_qwen ] || exit 22
printf '[%s] CONCURRENT_GPU_START user_authorized=true Gemini continues; latency may include contention\n' "$(date -Is)"
printf 'state=preflight\n' > "$RUN/launcher_status.txt"
python "$RUN/reuse_artifacts.py"
python - <<'PY'
import torch
x=torch.arange(16,device='cuda'); assert x.sum().item()==120
print('CUDA_OK',torch.__version__,torch.cuda.get_device_name(0),flush=True)
PY
PYTHONPATH="$RUN/test_deps:$PYTHONPATH" python -m pytest tests/test_qwen_runtime.py tests/test_asr_resilience.py tests/test_pipeline_optimizations.py tests/test_segment_resilience.py tests/test_warm_query.py tests/test_export_mandol.py -q > "$RUN/tests.log" 2>&1
sha256sum "$QWEN_MODEL_PATH"/*.safetensors "$QWEN_MODEL_PATH"/config.json > "$RUN/checkpoint_hashes.sha256"
python benchmarks/qwen_multimodal_server.py > "$RUN/server.log" 2>&1 &
server_pid=$!
trap 'rc=$?; kill "$server_pid" 2>/dev/null || true; printf "exit_status=%s\nfinished_at=%s\n" "$rc" "$(date -Is)" > "$RUN/launcher_status.txt"; exit "$rc"' EXIT
python - <<'PY'
import time,httpx
for i in range(180):
 try:
  r=httpx.get('http://127.0.0.1:8766/health');r.raise_for_status();assert r.json()['model']=='Qwen/Qwen3.5-4B';break
 except httpx.HTTPError:time.sleep(2)
else:raise RuntimeError('Qwen server did not become ready')
PY
bash "$RUN/preflight.sh"
printf 'state=running_pipeline\n' > "$RUN/launcher_status.txt"
bash "$RUN/run_pipeline.sh"
