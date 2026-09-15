#!/usr/bin/env bash
source /opt/streammeco/run/egolife_10q_gemini/environment.sh
exec > >(tee -a "$RUN/asr_repair.log") 2>&1
finish() {
 rc=$?
 trap - EXIT
 echo ASR_REPAIR_EXIT_STATUS=$rc
 echo "$rc" > "$RUN/asr_repair_exit_status.txt"
 if [ "$rc" -ne 0 ]; then
   printf 'exit_status=%s\nphase=asr_repair\nfinished_at=%s\n' "$rc" "$(date -Is)" > "$RUN/pipeline_status.txt"
 fi
 exit "$rc"
}
trap finish EXIT
printf 'exit_status=repairing\nphase=clip7_asr_retest\n' > "$RUN/pipeline_status.txt"
/opt/streammeco/mandol-venv/bin/python -m pytest -q tests/test_asr_resilience.py
python benchmarks/egolife_first10.py build --qa "$QA" --clips "$CLIPS" --results "$RESULTS" --work "$WORK" --max-segments 7
printf 'ASR_REPAIR_CLIP7_PASSED\n'
bash "$RUN/run_pipeline.sh"
