#!/usr/bin/env bash
set -Eeuo pipefail
RUN_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
SESSION=online-memory-sol-astra-20260918-preflight
command -v tmux >/dev/null
if tmux has-session -t "$SESSION" 2>/dev/null; then
  echo "Session already exists: $SESSION" >&2
  exit 1
fi
tmux new-session -d -s "$SESSION" -c "$RUN_ROOT"
tmux set-option -t "$SESSION" remain-on-exit on
tmux respawn-pane -k -t "$SESSION:0.0" "bash '$RUN_ROOT/scripts/run_preflight.sh'"
printf '%s\n' "$SESSION"
