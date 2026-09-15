#!/usr/bin/env bash
source /opt/streammeco/run/egolife_10q_gemini/environment.sh
exec > >(tee -a "$RUN/optimization_live_check.log") 2>&1
trap 'rc=$?; echo OPTIMIZATION_CHECK_EXIT_STATUS=$rc; if [ "$rc" -ne 0 ]; then printf "exit_status=%s\nphase=optimization_check\n" "$rc" > "$RUN/pipeline_status.txt"; fi' EXIT
printf 'exit_status=optimizing\nphase=live_measurement_check\n' > "$RUN/pipeline_status.txt"
python - <<'PY'
import pickle,json,time
from pathlib import Path
from benchmarks import egolife_first10
r=Path('/opt/streammeco/run/egolife_10q_gemini')
s=pickle.load((r/'work/build_state.pkl').open('rb'))
start=s['next_segment'];(r/'optimization_target.txt').write_text(str(start+1))
policy={'started_epoch':time.time(),'first_segment':start,'prefetch_ahead':2,'asr':'concurrent providers',
        'http':'persistent per-process pools with TCP/TLS event counts',
        'memory_embeddings':'one batch per clip; per-text latency unavailable',
        'timing':'per-call and stage timing plus queue/ordered/checkpoint events; overlapping stages not summed',
        'retrieval':'unchanged trial rules; no construction workers during retrieval evaluation'}
with (r/'results/execution_policies.jsonl').open('a') as f:f.write(json.dumps(policy)+'\n')
print('OPTIMIZATION_POLICY',json.dumps(policy),flush=True)
PY
TARGET=$(cat "$RUN/optimization_target.txt")
python benchmarks/egolife_first10.py build --qa "$QA" --clips "$CLIPS" --results "$RESULTS" --work "$WORK" --max-segments "$TARGET" --prefetch 2
python - <<'PY'
import json
from pathlib import Path
r=Path('/opt/streammeco/run/egolife_10q_gemini');target=int((r/'optimization_target.txt').read_text())
validated=0
for index in [target-1,target]:
 p=r/'results/clip_audits'/f'clip_{index}_audit.json'
 if not p.exists():continue # allowed cloud failures are recorded as skips
 x=json.loads(p.read_text());b=x['stage_details']['text_embedding_batch']
 assert b['timing_scope']=='whole_batch' and b['per_text_latency_ms'] is None
 assert b['input_count']==x['counts']['episodic_memories']+x['counts']['semantic_memories']
 assert b['latency_ms']==x['latency_ms']['text_embedding']
 assert len(b['calls'])>=1
 print('CLIP_BATCH_TIMING_VERIFIED',index,'texts=',b['input_count'],'ms=',b['latency_ms'],flush=True)
 validated+=1
assert validated, 'No completed segment available to validate optimized embedding path'
events=[json.loads(v) for v in (r/'results/segment_schedule_events.jsonl').read_text().splitlines()]
for e in events[-2:]:
 assert e['segment_latency_ms']>=e['ordered_stage_ms']>=0
 assert e['consumer_wait_ms']>=0 and e['ready_to_ordered_ms']>=0
print('OPTIMIZED_LIVE_MEASUREMENT_CHECK_PASSED',flush=True)
PY
bash "$RUN/run_pipeline.sh"
