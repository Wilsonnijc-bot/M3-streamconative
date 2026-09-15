"""Apply user query times while retaining safe committed memory and cached acquisition."""
import os,sys,json,pickle,hashlib,shutil
from pathlib import Path
sys.path.insert(0,os.environ['STREAMMECO_ROOT'])
from benchmarks.bedroom_benchmark import save_snapshot,write_json
run=Path(os.environ['RUN']);results=run/'results';work=run/'work'
archive=run/'provenance/query_schedule_change';archive.mkdir(parents=True,exist_ok=True)
with (work/'build_state.pkl').open('rb') as h:state=pickle.load(h)
assert len(state['completed'])==12
assert max(r['absolute_end_seconds'] for r in state['segment_map'].values())==360
for p in [run/'questions.json',results/'questions_without_gold.json',results/'segment_plan.json',run/'pipeline_status.txt']:
 if p.exists() and not (archive/p.name).exists():shutil.copy2(p,archive/p.name)
requested={f'Q{i:02d}':2163.0 for i in range(1,16)}
requested.update(Q09=102.0,Q01=440.0,Q08=440.0,Q10=705.0,Q11=1265.0)
effective={**requested,'Q09':90.0}
rows=json.loads((run/'questions_reference.json').read_text())
for row in rows:
 row['query_time']={'date':'VIDEO','time':effective[row['ID']]}
 row['requested_query_seconds']=requested[row['ID']]
 row['effective_query_seconds']=effective[row['ID']]
 row['timestamp_approximation_seconds']=effective[row['ID']]-requested[row['ID']]
write_json(rows,run/'questions.json')
# Recover Q09 from the immutable clip-3 graph, never from the current six-minute graph.
source=results/'clip_audits/clip_3_graph.pkl'
with source.open('rb') as h:graph=pickle.load(h)
safe_segments={i:r for i,r in state['segment_map'].items() if r['absolute_end_seconds']<=90}
assert set(safe_segments)=={1,2,3}
save_snapshot(graph,rows[8],9,safe_segments,results)
mdpath=results/'memory/q09_uncompressed/metadata.json';md=json.loads(mdpath.read_text())
md['requested_query_seconds']=102;md['effective_query_seconds']=90
md['approximation_reason']='Reuse saved 01:30 prefix, 12 seconds before requested 01:42; no future memory.'
md['recovered_from_clip_audit_sha256']=hashlib.sha256(source.read_bytes()).hexdigest()
write_json(md,mdpath)
manifest={'policy':'query-time snapshots; actual evaluation may run later against immutable earlier snapshots','requested_seconds':requested,'effective_seconds':effective,'reused_committed_segments':12,'recovered_snapshot':'Q09 from clip 3','expected_processing_segments':76,'source_clips':73,'cut_boundaries_seconds':[440,705,1265,2163]}
write_json(manifest,results/'query_schedule.json')
write_json(manifest,archive/'change_manifest.json')
plan=json.loads((results/'segment_plan.json').read_text());plan['query_end_seconds']=2163;plan['query_policy']='per-question effective timestamps in query_schedule.json';plan['expected_processing_segments']=76;write_json(plan,results/'segment_plan.json')
# Any unfinished model call remains visible but must not masquerade as a successful observation.
p=results/'gemini_calls.jsonl'
if p.exists():
 original=p.read_text();(archive/'gemini_calls_at_change.jsonl').write_text(original)
 events=[json.loads(s) for s in original.splitlines() if s.strip()]
 for e in events:
  if e.get('segment_id',0) and e['segment_id']>12 and not e.get('response'):
   e['error']='Interrupted intentionally for user query-timestamp change; segment not committed.'
 p.write_text(''.join(json.dumps(e,ensure_ascii=False)+'\n' for e in events))
print('SCHEDULE_APPLIED: 12 committed segments reused; Q09 snapshot verified at 90 s; 76 planned processing segments',flush=True)
