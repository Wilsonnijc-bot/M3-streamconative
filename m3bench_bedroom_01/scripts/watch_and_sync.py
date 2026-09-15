"""Durably observe the tmux run, refresh outputs and record verified completion."""
import subprocess,time,json,re,datetime
from pathlib import Path
from sync_run import ROOT,KEY,HOST,REMOTE
while True:
 try:
  subprocess.run(['python3',str(ROOT/'scripts/sync_run.py')],check=True)
  raw=ROOT/'provenance/raw/gemini'
  status=(raw/'pipeline_status.txt').read_text() if (raw/'pipeline_status.txt').exists() else ''
  match=re.search(r'^exit_status=(\d+)$',status,re.M)
  if match:
   code=int(match[1]);vpath=raw/'results/validation.json'
   validation=json.loads(vpath.read_text()) if vpath.exists() else {}
   log=(raw/'pipeline.log').read_text() if (raw/'pipeline.log').exists() else ''
   complete=code==0 and validation.get('status')=='complete' and validation.get('qa_rows')==60 and not validation.get('problems') and 'PIPELINE_COMPLETE' in log
   observed={'exit_status':code,'verified_complete':complete,'validation':validation,'observed_at':datetime.datetime.now(datetime.timezone.utc).isoformat()}
   (ROOT/'provenance/final_observation.json').write_text(json.dumps(observed,indent=2)+'\n')
   ledger=ROOT.parent/'experiment_GPU_record.md'
   text=ledger.read_text();marker='## M3-Bench bedroom_01 — Gemini four-method benchmark'
   start=text.index(marker);end=text.find('\n## ',start+3);end=len(text) if end<0 else end
   block=text[start:end]
   block=re.sub(r'\*\*Status:\*\*[^\n]*','**Status:** '+('completed; 60 validated answers and exit 0.' if complete else f'failed/incomplete; observed exit {code}, inspect provenance/final_observation.json.'),block,count=1)
   if complete:
    metrics=json.loads((raw/'results/aggregate_metrics.json').read_text())
    block+='\n- **Final model-judged scores:** '+', '.join(f"{m}={v['correct']}/{v['questions']}" for m,v in metrics.items())+'. Separate grading is excluded from QA timing.\n'
   ledger.write_text(text[:start]+block+text[end:])
   print(json.dumps(observed),flush=True)
   break
 except Exception as exc:print(type(exc).__name__+': '+str(exc),flush=True)
 time.sleep(180)
