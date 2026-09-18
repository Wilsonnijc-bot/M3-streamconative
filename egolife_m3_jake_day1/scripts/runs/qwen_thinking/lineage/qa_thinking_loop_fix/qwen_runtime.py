"""Audited, fail-closed local Qwen reasoning, shared by all benchmark methods."""
import json, os, time, uuid
from pathlib import Path
import cloud_http
MODEL='Qwen/Qwen3.5-4B'
CONTEXT={}
def append(event,name='qwen_calls.jsonl'):
 root=os.environ.get('EGOLIFE_RESULTS')
 if root:
  p=Path(root)/name;p.parent.mkdir(parents=True,exist_ok=True)
  with p.open('a') as f:f.write(json.dumps(event,ensure_ascii=False)+'\n')
def call(messages,purpose,max_tokens=16384,media=None):
 event=dict(CONTEXT,call_id=str(uuid.uuid4()),purpose=purpose,model=MODEL,provider='local CUDA',request_start=time.time(),ttft_ms=None,media=media)
 start=time.perf_counter()
 try:
  r=cloud_http.post(os.environ.get('QWEN_URL','http://127.0.0.1:8766/generate'),timeout=1800,json={'messages':messages,'purpose':purpose,'max_new_tokens':max_tokens,'context':event,'media':media})
  r.raise_for_status();body=r.json();event.update(body)
  if event.get('returned_model')!=MODEL:raise RuntimeError('Unexpected local checkpoint')
  if not event.get('response') or event.get('finish_reason')=='length':raise RuntimeError('Qwen returned empty/truncated output')
 except Exception as exc:
  event['error']=f'{type(exc).__name__}: {exc}';raise
 finally:
  event['request_end']=time.time();event['latency_ms']=(time.perf_counter()-start)*1000
  event['client_wall_clock_latency_ms']=event['latency_ms'];append(event)
 return event
def text_call(backend,prompt,qwen_url=None,purpose='final_answer'):
 if backend!='qwen':raise RuntimeError('Only local Qwen reasoning is permitted')
 return call([{'role':'user','content':prompt}],purpose)
def configure(results,phase):
 os.environ.pop('EGOLIFE_GEMINI_ONLY',None);os.environ['EGOLIFE_QWEN_ONLY']='1';os.environ['EGOLIFE_RESULTS']=str(results)
 CONTEXT.clear();CONTEXT.update(phase=phase,question_id=None,method=None)
 manifest={'reasoning_model':MODEL,'checkpoint':os.environ['QWEN_MODEL_PATH'],'provider':'local CUDA','execution_policy':'user-authorized concurrent GPU workers with Gemini; latency potentially contended','fallbacks':False,'memory_lineage':'fresh shared Qwen stream','vlm_fps':float(os.environ['QWEN_VLM_FPS']),'face_preprocessing_fps':5,'generation':{'thinking':True,'max_new_tokens':16384,'do_sample':False,'memory_repetition_penalty':1.08,'text_repetition_penalty':1.0},'prompt_change':'Qwen-only identity system prompt v2: preserve supplied speaker IDs and transcript coverage; unchanged shared base prompt and decoding','sampling':'same explicit timestamped JPEG image sequence as Gemini; no processor video resampling','ttft_ms':None,'cache_policy':'successful ASR only; cache read wall time separate from original provider acquisition'}
 p=Path(results)/'model_manifest.json';p.parent.mkdir(parents=True,exist_ok=True)
 if p.exists() and json.loads(p.read_text())!=manifest:raise RuntimeError('Incompatible Qwen generation/FPS lineage')
 p.write_text(json.dumps(manifest,indent=2)+'\n')
 print('REASONING_MODEL='+MODEL+' FPS='+str(manifest['vlm_fps'])+' fallbacks=disabled',flush=True)
