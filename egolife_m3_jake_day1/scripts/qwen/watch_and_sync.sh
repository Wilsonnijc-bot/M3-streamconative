#!/usr/bin/env bash
set -u
ROOT=/Users/nijiachen/StreamMeCo/egolife_m3_jake_day1
CASE=qwen_thinking
while true; do
 python3 "$ROOT/scripts/sync_run.py" "$CASE" || { sleep 30; continue; }
 if test -f "$ROOT/provenance/raw/$CASE/launcher_status.txt" && grep -Eq '^exit_status=[0-9]+$' "$ROOT/provenance/raw/$CASE/launcher_status.txt"; then break; fi
 sleep 30
done
