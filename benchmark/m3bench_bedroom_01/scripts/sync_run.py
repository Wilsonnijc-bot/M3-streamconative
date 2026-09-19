"""Sync only this M3-Bench experiment into its independent local result tree."""
import subprocess,os,json,datetime,fcntl
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
KEY='/Users/nijiachen/.ssh/streammeco_hyperstack_1042997';HOST='ubuntu@185.216.21.158'
REMOTE='/opt/streammeco/run/m3bench_bedroom_gemini'
def rsync(source,dest,flags=()):
 dest.mkdir(parents=True,exist_ok=True)
 subprocess.run(['rsync','-az','--keep-dirlinks','-e',f'ssh -i {KEY} -o BatchMode=yes -o ConnectTimeout=15',*flags,HOST+':'+source,str(dest)+'/'],check=True)
def sync():
 raw=ROOT/'provenance/raw/gemini'
 rsync(REMOTE+'/',raw,[f'--exclude={p}' for p in ['code/','smoke/','__pycache__/','results/asr_cache/','work/intermediate/','work/segments/','*_graph.pkl','*.py','*.sh']])
 exists=json.loads(subprocess.check_output(['ssh','-i',KEY,'-o','BatchMode=yes',HOST,"python3 -c 'import json;from pathlib import Path;r=Path(\""+REMOTE+"\");print(json.dumps({p:(r/p).exists() for p in [\"smoke\",\"results/asr_cache\",\"work/intermediate\"]}))'"],text=True))
 if exists['smoke']:
  rsync(REMOTE+'/smoke/',ROOT/'provenance/raw/preflight',['--exclude=__pycache__/','--exclude=*_graph.pkl'])
 if exists['results/asr_cache']:rsync(REMOTE+'/results/asr_cache/',ROOT/'cache/asr/gemini')
 if exists['work/intermediate']:
  for kind,pattern in [('faces','*_faces.json'),('voices','*_voices.json')]:
   rsync(REMOTE+'/work/intermediate/',ROOT/'cache'/kind/'gemini',['--prune-empty-dirs','--include=*/','--include='+pattern,'--exclude=*'])
 p=ROOT/'provenance/last_sync.json';p.write_text(json.dumps({'remote':HOST+':'+REMOTE,'synced_at':datetime.datetime.now(datetime.timezone.utc).isoformat()},indent=2)+'\n')
 subprocess.run(['python3',str(ROOT/'scripts/render_results.py')],check=True)
 print('BEDROOM_SYNC_COMPLETE',flush=True)
if __name__=='__main__':
 (ROOT/'provenance').mkdir(exist_ok=True)
 with (ROOT/'provenance/.sync.lock').open('w') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX);sync()
