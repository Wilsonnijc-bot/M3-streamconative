import json,pickle,hashlib,os
from pathlib import Path
r=Path(os.environ['QWEN_RUN']);source=Path('/opt/streammeco/run/egolife_10q_qwen35_4b_fps2_thinking_ids_v2')
from benchmarks import qwen_runtime
qwen_runtime.configure(r/'results','resume_verification')
s=pickle.load((r/'work/build_state.pkl').open('rb'))
assert s['reasoning_model']=='Qwen/Qwen3.5-4B'
assert len(s['completed'])>=2
for i in (1,2):
 assert s['segment_map'][i]['status']=='committed'
 p=r/f'results/clip_audits/clip_{i}_audit.json';original=source/f'results/clip_audits/clip_{i}_audit.json'
 assert p.read_bytes()==original.read_bytes()
 call=json.loads(p.read_text())['stage_details']['vlm']['attempts'][0]
 assert call['thinking_enabled'] and call['thinking_completed'] and call['vlm_fps']==2
for name in ['mmagent/qwen_memory_prompt.py','mmagent/prompts.py','mmagent/memory_processing_local_qwen.py','benchmarks/qwen_multimodal_server.py']:
 candidate = r/'lineage/qa_thinking_loop_fix/qwen_multimodal_server.py' if name=='benchmarks/qwen_multimodal_server.py' else r/'code/StreamMeCo'/name
 assert candidate.read_bytes()==(source/'code/StreamMeCo'/name).read_bytes()
record={'source_run':str(source),'adopted_committed_segments':[1,2],'source_checkpoint_sha256':hashlib.sha256((source/'work/build_state.pkl').read_bytes()).hexdigest(),'reasoning':'same Qwen identity prompt v2, thinking on, 2 FPS, same decoding; no baseline/Gemini memories','known_limitations':'Identity prompt test had incomplete episodic attribution in segment 2 and ASR provider-label confusion; user authorized full run with this prompt. These are retained quality findings, not overridden outputs.','latency':'Prefix retains original measured timings; restarted server warmup excluded; concurrent GPU contention remains possible.'}
(r/'memory_resume_manifest.json').write_text(json.dumps(record,indent=2)+'\n')
print('RESUME_LINEAGE_VERIFIED prefix_segments=2 current_completed='+str(len(s['completed'])),flush=True)
