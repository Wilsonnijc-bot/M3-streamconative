#!/usr/bin/env bash
set -Eeuo pipefail
case "$1" in
 egolife) source /opt/streammeco/run/egolife_10q_gemini/environment.sh; entry="$MANDOL/benchmarks/egolife_m3_first10.py" ;;
 bedroom) source /opt/streammeco/run/m3bench_bedroom_gemini/environment.sh; entry="$MANDOL/benchmarks/bedroom_mandol.py" ;;
 *) exit 2 ;;
esac
export RUN SMC MANDOL RESULTS WORK QA CLIPS
variant="$RUN/reruns/mandol_100_20"
mkdir -p "$variant"
exec 9>"$variant/run.lock"
flock -n 9 || exit 20
exec >>"$variant/pipeline.log" 2>&1
finish() { rc=$?; printf 'exit_status=%s\nfinished_at=%s\n' "$rc" "$(date -Is)" > "$variant/exit_status.txt"; }
trap finish EXIT
printf 'exit_status=running\nstarted_at=%s\n' "$(date -Is)" > "$variant/exit_status.txt"
cd "$MANDOL"
/opt/streammeco/mandol-venv/bin/python /opt/streammeco/run/m3bench_bedroom_gemini/rerun_mandol_budget.py --dataset "$1" --entrypoint "$entry"
