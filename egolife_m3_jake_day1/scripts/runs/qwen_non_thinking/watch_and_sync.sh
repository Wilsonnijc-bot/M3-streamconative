#!/usr/bin/env bash
set -u
DEST=/Users/nijiachen/StreamMeCo/egolife_m3_jake_day1/provenance/raw/qwen_non_thinking
mkdir -p "$DEST"
while true; do
 rsync -az -e 'ssh -i /Users/nijiachen/.ssh/streammeco_hyperstack_1042997 -o BatchMode=yes' --exclude code --exclude 'work/intermediate/' --exclude 'work/segments/' ubuntu@185.216.21.158:/opt/streammeco/run/egolife_10q_qwen35_4b_fps2/ "$DEST/"
 if test -f "$DEST/launcher_status.txt" && rg -q '^exit_status=[0-9]+$' "$DEST/launcher_status.txt"; then break; fi
 sleep 30
done
