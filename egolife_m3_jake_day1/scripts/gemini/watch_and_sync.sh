#!/usr/bin/env bash
# Mac storage/orchestration only. Remote inference is never restarted by this watcher.
set -uo pipefail
ROOT=/Users/nijiachen/StreamMeCo/egolife_m3_jake_day1
DEST=$ROOT/provenance/raw/gemini
mkdir -p "$DEST"
LOCK=$DEST/.sync_watcher_lock
mkdir "$LOCK" 2>/dev/null || exit 0
trap 'rmdir "$LOCK"' EXIT
printf '%s\n' "$$" > "$DEST/sync_watcher.pid"
last_sync=0
while true; do
 if remote_status=$(ssh -i /Users/nijiachen/.ssh/streammeco_hyperstack_1042997 -o BatchMode=yes -o ConnectTimeout=15 ubuntu@185.216.21.158 'cat /opt/streammeco/run/egolife_10q_gemini/pipeline_status.txt' 2>> "$DEST/sync_watcher.log"); then
  printf '%s\n' "$remote_status" > "$DEST/last_remote_status.txt"
  now=$(date +%s)
  finished=false
  if printf '%s\n' "$remote_status" | grep -Eq '^exit_status=[0-9]+$'; then finished=true; fi
  if "$finished" || [ $((now-last_sync)) -ge 300 ]; then
   if python3 "$ROOT/scripts/sync_run.py" gemini; then
    last_sync=$now
    printf 'Artifacts and Markdown refreshed at %s\n%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$remote_status" > "$DEST/sync_status.txt"
    if "$finished"; then exit 0; fi
   fi
  fi
 fi
 sleep 30
done
