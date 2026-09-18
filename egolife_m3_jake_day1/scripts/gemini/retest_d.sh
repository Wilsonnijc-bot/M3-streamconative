#!/usr/bin/env bash
source /opt/streammeco/run/egolife_10q_gemini/environment.sh
exec > >(tee "$RUN/retest_d.log") 2>&1
trap 'rc=$?; echo D_TIMING_TEST_EXIT_STATUS=$rc; echo "$rc" > "$RUN/retest_d_exit_status.txt"' EXIT
TEST=$RUN/smoke/results
mkdir -p "$RUN/smoke/prior_attempts"
mv "$TEST/method_D_mandol.jsonl" "$RUN/smoke/prior_attempts/method_D_initial_timing.jsonl"
cd "$MANDOL"
source /opt/streammeco/mandol-venv/bin/activate
python benchmarks/egolife_m3_first10.py eval --qa "$QA" --results "$TEST" --limit 1 --backend openai
python - <<'PY'
import json
from pathlib import Path
x=json.loads(Path('/opt/streammeco/run/egolife_10q_gemini/smoke/results/method_D_mandol.jsonl').read_text())
r=x['retrieval_rounds'][0]['retrieval']
assert r['dense_ms']>0 and r['memory_unit_lookup_ms']>0 and r['fusion_ms']>0
assert len(r['backend_calls'])==3 and x['retrieval_round_count']==1
assert x['prediction'] in ['A','B','C','D'] and x['retrieved_node_ids']
print('MANDOL_DETAILED_TIMING_TEST_PASSED',flush=True)
PY
