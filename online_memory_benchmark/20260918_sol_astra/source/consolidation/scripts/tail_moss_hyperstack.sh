#!/usr/bin/env bash
set -Euo pipefail
cd /opt/streammeco/run/consolidation_live
export PYTHONPATH="/opt/streammeco/run/consolidation_live/deps:/opt/streammeco/repos/MOSS-Transcribe-Diarize:$PWD"
export PYTHONUTF8=1 LANG=C.UTF-8 LC_ALL=C.UTF-8 OMP_NUM_THREADS=8
/opt/streammeco/.venv/bin/python -u -m consolidation.moss_tail \
 --folder results/prefix_40 --checkpoint /opt/streammeco/models/MOSS-Transcribe-Diarize \
 2>&1 | tee tail.log
rc=${PIPESTATUS[0]}
printf '\nEXIT_STATUS=%s\n' "$rc" | tee -a tail.log
printf '%s\n' "$rc" > tail_exit_status.txt
exit "$rc"
