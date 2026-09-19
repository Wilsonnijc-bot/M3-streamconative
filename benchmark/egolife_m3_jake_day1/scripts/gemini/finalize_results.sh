#!/usr/bin/env bash
source /opt/streammeco/run/egolife_10q_gemini/environment.sh
exec > >(tee -a "$RUN/finalize_results.log") 2>&1
finish() {
 rc=$?
 trap - EXIT
 printf 'exit_status=%s\nphase=finalization\nfinished_at=%s\n' "$rc" "$(date -Is)" > "$RUN/pipeline_status.txt"
 echo FINALIZATION_EXIT_STATUS=$rc
 exit "$rc"
}
trap finish EXIT
/opt/streammeco/mandol-venv/bin/python -m pytest -q tests/test_gemini_report.py
COMMON=(--qa "$QA" --results "$RESULTS" --work "$WORK")
python benchmarks/egolife_first10.py report "${COMMON[@]}"
python benchmarks/egolife_first10.py validate "${COMMON[@]}"
echo BENCHMARK_FINALIZATION_COMPLETE
