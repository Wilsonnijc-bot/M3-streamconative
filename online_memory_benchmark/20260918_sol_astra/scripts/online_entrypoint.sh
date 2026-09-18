#!/usr/bin/env bash
set -Eeuo pipefail
RUN_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$RUN_ROOT"
set -a
source /opt/streammeco/secrets/online_memory.env
set +a
export PYTHONUTF8=1 PYTHONHASHSEED=0
export PYTHONPATH="$RUN_ROOT/source/StreamMeCo:$RUN_ROOT/source:$RUN_ROOT/source/Mandol/src:/opt/streammeco/repos/3D-Speaker"
export ONLINE_PRIMARY_MODEL=gpt-5.6-terra ONLINE_PRIMARY_REASONING_EFFORT=medium
export ONLINE_CONSOLIDATION_MODEL=gpt-5.6-sol ONLINE_CONSOLIDATION_REASONING_EFFORT=high
/opt/streammeco/.venv/bin/python -u scripts/preflight.py
/opt/streammeco/.venv/bin/python -u scripts/launch_gate.py
exec /opt/streammeco/.venv/bin/python -u scripts/online_benchmark.py --run-root "$RUN_ROOT" --results "$RUN_ROOT/results" --resume
