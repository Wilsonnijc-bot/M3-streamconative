"""Route remote artifacts into the shared result contract; no inference on Mac."""
import argparse,json,os,subprocess,shlex,shutil,datetime,fcntl
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
RUNS={'gemini':'egolife_10q_gemini','qwen_non_thinking':'egolife_10q_qwen35_4b_fps2',
      'qwen_thinking':'egolife_10q_qwen35_4b_fps2_thinking_ids_v2_full','qwen_thinking_baseline':'egolife_10q_qwen35_4b_fps2_thinking','qwen_identity_v2':'egolife_10q_qwen35_4b_fps2_thinking_ids_v2'}
KEY='/Users/nijiachen/.ssh/streammeco_hyperstack_1042997';HOST='ubuntu@185.216.21.158'

def rsync(source,dest,extra=()):
 dest.mkdir(parents=True,exist_ok=True)
 subprocess.run(['rsync','-az','--keep-dirlinks','-e',f'ssh -i {shlex.quote(KEY)} -o BatchMode=yes',*extra,HOST+':'+source,str(dest)+'/'],check=True)

def cache_alias(alias,dest):
 if alias.is_dir() and not alias.is_symlink() and all(p.is_symlink() for p in alias.iterdir()):
  shutil.rmtree(alias) # only relocated aliases; canonical cache files are untouched
 if not alias.exists() and not alias.is_symlink():
  alias.parent.mkdir(parents=True,exist_ok=True)
  alias.symlink_to(os.path.relpath(dest,alias.parent),target_is_directory=True)

def sync(case,render=True):
 remote='/opt/streammeco/run/'+RUNS[case]+'/'
 raw=ROOT/'provenance/raw'/case
 exclusions=['code/','test_deps/','__pycache__/','asr_cache/','work/intermediate/','work/segments/','preflight_review/','*_graph.pkl','*.py','*.sh']
 rsync(remote,raw,[f'--exclude={x}' for x in exclusions])
 rsync(remote,ROOT/'scripts/runs'/case,['--exclude=code/','--exclude=test_deps/','--exclude=__pycache__/','--prune-empty-dirs','--include=*/','--include=*.py','--include=*.sh','--exclude=*'])
 paths=['results/asr_cache','work/intermediate','work/segments']
 code='import json;from pathlib import Path;print(json.dumps({p:Path('+repr(remote)+'+p).exists() for p in '+repr(paths)+'}))'
 result=subprocess.run(['ssh','-i',KEY,'-o','BatchMode=yes',HOST,'python3 -c '+shlex.quote(code)],check=True,capture_output=True,text=True)
 exists=json.loads(result.stdout)
 if exists['results/asr_cache']:
  dest=ROOT/'cache/asr'/case/'results';rsync(remote+'results/asr_cache/',dest,['-L'])
  alias=raw/'results/asr_cache'
  cache_alias(alias,dest)
 if exists['work/intermediate']:
  for kind,pattern in [('faces','*_faces.json'),('voices','*_voices.json')]:
   dest=ROOT/'cache'/kind/case/'work/intermediate'
   rsync(remote+'work/intermediate/',dest,['-L','--prune-empty-dirs','--include=*/','--include='+pattern,'--exclude=*'])
   for p in dest.rglob('*.json'):
    alias=raw/'work/intermediate'/p.relative_to(dest);alias.parent.mkdir(parents=True,exist_ok=True)
    if not alias.exists() and not alias.is_symlink():alias.symlink_to(os.path.relpath(p,alias.parent))
 if exists['work/segments']:
  dest=ROOT/'cache/media'/case/'work/segments';rsync(remote+'work/segments/',dest,['-L'])
  alias=raw/'work/segments';alias.parent.mkdir(parents=True,exist_ok=True)
  cache_alias(alias,dest)
 if case=='qwen_thinking':
  dest=ROOT/'cache/graphs'/case/'results/clip_audits'
  rsync(remote+'results/clip_audits/',dest,['--prune-empty-dirs','--include=*/','--include=*_graph.pkl','--exclude=*'])
  for p in dest.glob('*_graph.pkl'):
   alias=raw/'results/clip_audits'/p.name
   if not alias.exists() and not alias.is_symlink():alias.symlink_to(os.path.relpath(p,alias.parent))
 if case=='gemini':
  # Keep native state for the final construction and latest query snapshot.
  # JSON views omit identity mappings and chronological indexes.
  audits=list((raw/'results/clip_audits').glob('clip_*_graph.json'))
  snapshots=sorted((raw/'results/memory').glob('q*_uncompressed'))
  selected=[]
  if audits:selected.append(max(audits,key=lambda p:int(p.stem.split('_')[1])).with_suffix('.pkl'))
  if snapshots:selected.append(snapshots[-1]/'graph.pkl')
  for alias in selected:
   relative=alias.relative_to(raw)
   dest=ROOT/'cache/graphs'/case/relative.parent
   rsync(remote+str(relative),dest)
   if not alias.exists() and not alias.is_symlink():alias.symlink_to(os.path.relpath(dest/alias.name,alias.parent))
 # Use the current remote status as an observation, not stale launcher success as benchmark completion.
 status=raw/'pipeline_status.txt'
 if not status.exists():status=raw/'launcher_status.txt'
 syncmeta=ROOT/'provenance/sync'/f'{case}.json';syncmeta.parent.mkdir(parents=True,exist_ok=True)
 syncmeta.write_text(json.dumps({'source':HOST+':'+remote,'synced_at':datetime.datetime.now(datetime.timezone.utc).isoformat()},indent=2)+'\n')
 if render:
  subprocess.run(['python3',str(ROOT/'scripts/render_results.py')],check=True)
 print('SYNCED',case,flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('case',choices=RUNS);p.add_argument('--no-render',action='store_true');a=p.parse_args()
 with (ROOT/'provenance'/f'.sync_{a.case}.lock').open('w') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX)
  sync(a.case,not a.no_render)
