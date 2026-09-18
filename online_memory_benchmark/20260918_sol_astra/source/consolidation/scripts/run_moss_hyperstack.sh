#!/usr/bin/env bash
set -Euo pipefail
cd /opt/streammeco/run/consolidation_live
export PYTHONPATH="/opt/streammeco/run/consolidation_live/deps:/opt/streammeco/repos/MOSS-Transcribe-Diarize:$PWD"
export OMP_NUM_THREADS=8
export LANG=C.UTF-8
export LC_ALL=C.UTF-8
export PYTHONUTF8=1
/opt/streammeco/.venv/bin/python -u -m consolidation.moss_local \
  --manifest metadata/prefix_20.json metadata/prefix_40.json \
  --media-root /opt/streammeco/data/egolife_day1 \
  --checkpoint /opt/streammeco/models/MOSS-Transcribe-Diarize \
  --revision 704aa4a9c304e8520be88901e0d1960158ef5b15 --output results \
  2>&1 | tee moss.log
rc=${PIPESTATUS[0]}
printf '\nEXIT_STATUS=%s\n' "$rc" | tee -a moss.log
printf '%s\n' "$rc" > exit_status.txt
exit "$rc"
