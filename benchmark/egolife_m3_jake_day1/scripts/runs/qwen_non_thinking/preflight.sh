#!/usr/bin/env bash
source /opt/streammeco/run/egolife_10q_qwen35_4b_fps2/environment.sh
exec > >(tee -a "$RUN/preflight.log") 2>&1
trap 'rc=$?; echo PREFLIGHT_EXIT_STATUS=$rc; echo "$rc" > "$RUN/preflight_exit_status.txt"' EXIT
python - <<'PY'
import torch
from benchmarks import qwen_runtime as r
from pathlib import Path
r.configure(Path('/opt/streammeco/run/egolife_10q_qwen35_4b_fps2/results'), 'preflight')
x=torch.arange(16, device='cuda'); assert x.sum().item()==120
print('CUDA_OK', torch.__version__, torch.cuda.get_device_name(0), flush=True)
a=r.text_call('qwen','Return exactly OK.',purpose='endpoint_preflight')
print('QWEN_ENDPOINT_OK', a['model'], a['returned_model'], a['response'], flush=True)
PY
python benchmarks/egolife_first10.py build --qa "$QA" --clips "$CLIPS" --results "$RESULTS" --work "$WORK" --max-segments 3
python - <<'PY'
from benchmarks import egolife_first10 as b
from pathlib import Path
import pickle
root=Path('/opt/streammeco/run/egolife_10q_qwen35_4b_fps2')
s=pickle.load((root/'work/build_state.pkl').open('rb'))
assert s['reasoning_model']=='Qwen/Qwen3.5-4B' and len(s['completed'])==3
assert all(x.get('status')=='committed' for x in s['segment_map'].values())
import json
for i in range(1,4):
 a=json.loads((root/'results/clip_audits'/f'clip_{i}_audit.json').read_text())
assert json.loads((root/'results/segment_plan.json').read_text())['segments']==144
q,_=b.load_questions(Path('/opt/streammeco/data/EgoLifeQA_A1_JAKE.json'))
b.save_snapshot(s['graph'], q[0], 1, s['segment_map'], root/'smoke/results')
print('QWEN_MEMORY_PREFLIGHT_OK segments=3',flush=True)
PY
TEST=$RUN/smoke/results
COMMON=(--qa "$QA" --results "$TEST" --work "$RUN/smoke/work" --limit 1)
python benchmarks/egolife_first10.py compress "${COMMON[@]}"
python benchmarks/egolife_first10.py export-mandol "${COMMON[@]}"
for method in A B C; do
 python benchmarks/egolife_first10.py eval "${COMMON[@]}" --method "$method" --backend qwen
done
deactivate
cd "$MANDOL"
source /opt/streammeco/mandol-venv/bin/activate
python benchmarks/egolife_m3_first10.py adapt --qa "$QA" --results "$TEST" --limit 1
python benchmarks/egolife_m3_first10.py eval --qa "$QA" --results "$TEST" --limit 1 --backend qwen
python - <<'PY'
import json
from pathlib import Path
r=Path('/opt/streammeco/run/egolife_10q_qwen35_4b_fps2/smoke/results')
for method in 'ABCD':
 p=list(r.glob(f'method_{method}_*.jsonl')); assert len(p)==1
 rows=[json.loads(x) for x in p[0].read_text().splitlines()]; assert len(rows)==1
 x=rows[0]; assert x['prediction'] in 'ABCD' and x['retrieved_node_ids']
 assert x['final_answer_call']['returned_model']=='Qwen/Qwen3.5-4B'
 if method!='A': assert x['retrieval_round_count']==1 and not x['controller_calls']
 print('RETRIEVAL_PREFLIGHT_OK',method,x['retrieval_round_count'],flush=True)
(r/'preflight_validation.json').write_text(json.dumps({'status':'passed','methods':list('ABCD'),'scope':'three-clip smoke; not benchmark QA results'}))
PY
echo ALL_PREFLIGHTS_PASSED
