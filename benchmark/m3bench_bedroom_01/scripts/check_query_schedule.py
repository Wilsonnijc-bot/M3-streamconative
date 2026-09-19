import os,sys,json,pickle
from pathlib import Path
sys.path.insert(0,os.environ['STREAMMECO_ROOT'])
from benchmarks import bedroom_benchmark as b
run=Path(os.environ['RUN']);questions,_=b.load_questions(run/'questions.json')
clips=sorted(Path(os.environ['CLIPS']).glob('bedroom_01_????????.mp4'))
last=max(q['query_time']['time'] for q in questions)
plan=[]
for pos,src in enumerate(clips):
 start=b.clock_seconds(b.clip_clock(src))
 end=min(start+b.media_duration(src),b.clock_seconds(b.clip_clock(clips[pos+1])) if pos+1<len(clips) else float('inf'),last)
 cuts=sorted({q['query_time']['time'] for q in questions if start<q['query_time']['time']<end})+[end]
 offset=0
 for boundary in cuts:
  finish=boundary-start
  if finish-offset>=.01:plan.append({'source':src.name,'clock':b.clip_clock(src),'offset':offset,'end':finish,'absolute_end':boundary})
  offset=finish
 if end==last:break
assert len(plan)==76,len(plan)
with (run/'work/build_state.pkl').open('rb') as h:state=pickle.load(h)
for i,r in state['segment_map'].items():
 p=plan[i-1]
 assert p['source']==r['source'] and p['offset']==r['start_seconds_in_source'] and p['end']==r['end_seconds_in_source']
assert all(q['query_time']['time'] in {p['absolute_end'] for p in plan} for q in questions)
md=json.loads((run/'results/memory/q09_uncompressed/metadata.json').read_text())
assert md['query_time_seconds']==90 and md['question']['id']=='Q09'
assert max(s['absolute_end_seconds'] for s in md['source_segments'])==90
assert [q['ID'] for q in questions]==[f'Q{i:02d}' for i in range(1,16)]
assert len({q['query_time']['time'] for q in questions})==5
b.write_json({'status':'passed','committed_prefix_preserved':len(state['completed']),'processing_segments':len(plan),'all_question_cutoffs_have_boundaries':True,'Q09_no_future_leakage':True,'plan':plan},run/'results/query_schedule_validation.json')
print('PASS: 12-segment checkpoint matches new plan; 76 segments; all 15 cutoffs available; Q09 has no future memory',flush=True)
