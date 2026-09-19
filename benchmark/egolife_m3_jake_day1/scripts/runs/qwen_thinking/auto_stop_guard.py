"""Publish hibernation readiness after complete validated QA."""
import argparse,datetime,hashlib,json
from pathlib import Path
RUN=Path('/opt/streammeco/run/egolife_10q_qwen35_4b_fps2_thinking_ids_v2_full')
GEMINI=Path('/opt/streammeco/run/egolife_10q_gemini')
NAMES=['method_A_normal_streammeco.jsonl','method_B_streammeco_oneshot.jsonl','method_C_compressed_oneshot.jsonl','method_D_mandol.jsonl']
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def check(run=RUN,gemini=GEMINI):
 for path in [run/'pipeline_status.txt',run/'launcher_status.txt']:
  if not path.exists() or 'exit_status=0' not in path.read_text().splitlines():return None,'waiting for successful Qwen pipeline and launcher exit'
 gp=gemini/'pipeline_status.txt'
 if not gp.exists() or 'exit_status=0' not in gp.read_text().splitlines():return None,'waiting for successful Gemini exit'
 r=run/'results';v=json.loads((r/'validation.json').read_text())
 if v.get('status')!='complete' or v.get('qa_rows')!=40 or v.get('problems'):return None,'waiting for successful 40-row validation'
 files=['pipeline_status.txt','launcher_status.txt','results/validation.json','results/model_manifest.json','results/snapshot_provenance.json','results/comparison.csv','results/comparison.md','results/aggregate_metrics.json','results/qwen_calls.jsonl','results/asr_calls.jsonl','results/embedding_batch_calls.jsonl','results/memory_construction_latency.jsonl','results/segment_schedule_events.jsonl','results/retrieval_warmup.jsonl','results/detailed_retrieval_events.jsonl','results/compression_metrics.json','results/mandol_retrieval_config.json']
 for name in NAMES:
  p=r/name;rows=[json.loads(l) for l in p.read_text().splitlines() if l.strip()]
  if sorted(x['question_index'] for x in rows)!=list(range(1,11)):return None,'incomplete or duplicate question rows in '+name
  if any(x.get('prediction') not in ['A','B','C','D'] for x in rows):return None,'invalid predictions in '+name
  files.append('results/'+name)
 for i in range(1,11):
  for kind,path in [('memory',f'memory/q{i:02d}_uncompressed'),('compression',f'streammeco_compressed/q{i:02d}')]:
   files.extend('results/'+path+'/'+n for n in ['graph.pkl','metadata.json'])
 for p in (r/'mandol_adapted').rglob('*'):
  if p.is_file():files.append(str(p.relative_to(run)))
 if not (r/'mandol_adapted/q10').is_dir():return None,'missing Mandol snapshots'
 manifest={}
 for name in sorted(set(files)):
  p=run/name
  if not p.is_file() or p.stat().st_size==0:return None,'missing/empty required artifact '+name
  manifest[name]=digest(p)
 return manifest,'results complete; waiting for verified Mac copy'
def main():
 a=argparse.ArgumentParser();a.add_argument('--check-only',action='store_true');args=a.parse_args()
 status={'instance_id':1042997,'updated_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'action':'Hyperstack hibernate after verified Mac copy'}
 try:
  manifest,message=check();status['state']=message
  if manifest:
   payload={'instance_id':1042997,'files':manifest};canonical=json.dumps(payload,sort_keys=True).encode();sha=hashlib.sha256(canonical).hexdigest();payload['manifest_sha256']=sha
   (RUN/'shutdown_ready_manifest.json').write_text(json.dumps(payload,indent=2)+'\n')
   receipt=RUN/'shutdown_copy_verified.json'
   if receipt.exists() and json.loads(receipt.read_text()).get('manifest_sha256')==sha:
    status['state']='ready_to_hibernate'
   else:
    status['state']='results complete; waiting for verified Mac copy'
 except Exception as e:status['state']='waiting_or_error';status['detail']=str(e)
 (RUN/'auto_stop_status.json').write_text(json.dumps(status,indent=2)+'\n');print(json.dumps(status),flush=True)
if __name__=='__main__':main()
