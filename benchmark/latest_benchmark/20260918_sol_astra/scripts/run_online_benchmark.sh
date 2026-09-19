#!/usr/bin/env bash
set -Eeuo pipefail
RUN_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$RUN_ROOT"
mkdir -p logs metadata results
RUN_ID="${ONLINE_RUN_ID:?ONLINE_RUN_ID must identify this launch}"
LOG="logs/${RUN_ID}.log"
STATUS="metadata/${RUN_ID}.status"
printf 'running\n' > "$STATUS"
printf '%s\n' "$LOG" > metadata/current_log.txt
set +e
bash scripts/online_entrypoint.sh 2>&1 | tee "$LOG"
rc=${PIPESTATUS[0]}
set -e
printf '\nEXIT_STATUS=%s\n' "$rc" >> "$LOG"
printf '%s\n' "$rc" > "metadata/${RUN_ID}.exit_status"
if [[ "$rc" -eq 0 ]]; then printf 'completed\n' > "$STATUS"; else printf 'failed\n' > "$STATUS"; fi
exit "$rc"
