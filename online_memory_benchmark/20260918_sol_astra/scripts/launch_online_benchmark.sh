#!/usr/bin/env bash
set -Eeuo pipefail
RUN_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
SESSION="${1:-online-memory-terra-sol-20260918-full-02}"
[[ "$SESSION" =~ ^[a-zA-Z0-9_-]+$ ]] || { echo 'Invalid session name' >&2; exit 2; }
command -v tmux >/dev/null
if tmux has-session -t "$SESSION" 2>/dev/null; then echo "Session already exists: $SESSION" >&2; exit 1; fi
# Launch directly; no empty live shell can be mistaken for a benchmark worker.
tmux new-session -d -s "$SESSION" -c "$RUN_ROOT" "ONLINE_RUN_ID='$SESSION' bash '$RUN_ROOT/scripts/run_online_benchmark.sh'"
tmux set-option -t "$SESSION" remain-on-exit on
printf '%s\n' "$SESSION" > "$RUN_ROOT/metadata/current_session.txt"
printf '%s\n' "$SESSION"
