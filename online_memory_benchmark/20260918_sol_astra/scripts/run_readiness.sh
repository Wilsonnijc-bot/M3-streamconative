#!/usr/bin/env bash
set -Eeuo pipefail
RUN_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$RUN_ROOT"
source /opt/streammeco/secrets/online_memory.env
export PYTHONUTF8=1
set +e
/opt/streammeco/.venv/bin/python -u scripts/preflight.py 2>&1 | tee logs/readiness.log
rc=${PIPESTATUS[0]}
set -e
printf '%s\n' "$rc" > metadata/readiness_exit_status.txt
exit "$rc"
