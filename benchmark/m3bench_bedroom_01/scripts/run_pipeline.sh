#!/usr/bin/env bash
source /opt/streammeco/run/m3bench_bedroom_gemini/environment.sh
exec 9>"$RUN/pipeline.lock"
flock -n 9 || exit 20
exec > >(tee -a "$RUN/pipeline.log") 2>&1
finish() { rc=$?; trap - EXIT; printf 'exit_status=%s\nfinished_at=%s\n' "$rc" "$(date -Is)" > "$RUN/pipeline_status.txt"; printf 'PIPELINE_EXIT_STATUS=%s\n' "$rc"; exit "$rc"; }
trap finish EXIT
[ -n "${TMUX:-}" ] && [ "$(tmux display-message -p '#S')" = m3bench_bedroom_gemini ]
printf 'exit_status=running\nstarted_at=%s\n' "$(date -Is)" > "$RUN/pipeline_status.txt"
phase() { name=$1; shift; printf '[%s] PHASE_START %s\n' "$(date -Is)" "$name"; "$@"; printf '[%s] PHASE_COMPLETE %s\n' "$(date -Is)" "$name"; }
while [ ! -f "$RUN/prepare_exit_status.txt" ]; do sleep 15; done
[ "$(cat "$RUN/prepare_exit_status.txt")" = 0 ]
COMMON=(--qa "$QA" --results "$RESULTS" --work "$WORK" --limit 15)
if [ ! -f "$RUN/smoke/passed.json" ]; then
 phase first_segment python benchmarks/bedroom_benchmark.py build --clips "$CLIPS" "${COMMON[@]}" --max-segments 1
 phase smoke_snapshot python "$RUN/smoke_snapshot.py"
 SMOKE=(--qa "$RUN/smoke/questions.json" --results "$RUN/smoke/results" --work "$RUN/smoke/work" --limit 1)
 phase smoke_compression python benchmarks/bedroom_benchmark.py compress "${SMOKE[@]}"
 phase smoke_export python benchmarks/bedroom_benchmark.py export-mandol "${SMOKE[@]}"
 for method in A B C; do phase "smoke_$method" python benchmarks/bedroom_benchmark.py eval "${SMOKE[@]}" --method "$method"; done
 deactivate; cd "$MANDOL"; source /opt/streammeco/mandol-venv/bin/activate
 phase smoke_adapt python benchmarks/bedroom_mandol.py adapt --qa "$RUN/smoke/questions.json" --results "$RUN/smoke/results" --limit 1
 phase smoke_D python benchmarks/bedroom_mandol.py eval --qa "$RUN/smoke/questions.json" --results "$RUN/smoke/results" --limit 1
 deactivate; cd "$SMC"; source /opt/streammeco/.venv/bin/activate
 python "$RUN/validate_smoke.py"
fi
phase memory_build python benchmarks/bedroom_benchmark.py build --clips "$CLIPS" "${COMMON[@]}"
phase compression python benchmarks/bedroom_benchmark.py compress "${COMMON[@]}"
phase mandol_export python benchmarks/bedroom_benchmark.py export-mandol "${COMMON[@]}"
phase parallel_evaluation python "$RUN/parallel_workers.py" --methods A B C D
python "$RUN/parallel_workers.py" --join
phase grading python "$RUN/grade_answers.py"
phase report python benchmarks/bedroom_benchmark.py report "${COMMON[@]}"
phase validate python benchmarks/bedroom_benchmark.py validate "${COMMON[@]}"
echo PIPELINE_COMPLETE
