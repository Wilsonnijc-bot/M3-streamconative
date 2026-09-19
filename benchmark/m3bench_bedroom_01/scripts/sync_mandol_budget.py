"""Sync the selected D100/20 results into the existing A/B/C/D reports."""
import argparse,hashlib,json,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
HOST='ubuntu@185.216.21.158';KEY='/Users/nijiachen/.ssh/streammeco_hyperstack_1042997'
CASES={'egolife':('egolife_m3_jake_day1','egolife_10q_gemini',10),
       'bedroom':('benchmark/m3bench_bedroom_01','m3bench_bedroom_gemini',15)}
SELECTED=['method_D_mandol.jsonl','method_D_selection.json','aggregate_metrics.json',
          'comparison.csv','comparison.md','detailed_retrieval_events.jsonl',
          'detailed_latency_events.jsonl','gemini_calls.jsonl','retrieval_warmup.jsonl',
          'validation.json','snapshot_provenance.json']
def rsync(source,dest,flags=()):
 dest.mkdir(parents=True,exist_ok=True)
 subprocess.run(['rsync','-az','-e','ssh -i '+KEY+' -o BatchMode=yes -o ConnectTimeout=10',
                 *flags,HOST+':'+source,str(dest)+'/'],check=True)
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--no-sync',action='store_true');args=parser.parse_args()
 for case,(local,remote,expected) in CASES.items():
  base=ROOT/local;raw=base/'provenance/raw/gemini';result=raw/'results'
  if not args.no_sync:
   rsync('/opt/streammeco/run/'+remote+'/reruns/mandol_100_20/',raw/'reruns/mandol_100_20',['--exclude=results/mandol_adapted/'])
   rsync('/opt/streammeco/run/'+remote+'/results/',result,
         ['--include='+name for name in SELECTED]+['--exclude=*'])
  config=json.loads((result/'method_D_selection.json').read_text())
  data=(result/'method_D_mandol.jsonl').read_bytes()
  assert hashlib.sha256(data).hexdigest()==config['source_sha256']
  rows=[json.loads(line) for line in data.splitlines()]
  assert len(rows)==expected and all(x['top_k']==20 and len(x['retrieved_evidence'])==20 for x in rows)
  variant=raw/'reruns/mandol_100_20'
  assert (variant/'baseline_method_D_2nodes.jsonl').is_file()
  # Both standard renderers now consume the promoted canonical D rows.
  command='import sys;sys.path.insert(0,'+repr(str(base/'scripts'))+');import render_results as r;r.render_case(r.RAW/"gemini")'
  subprocess.run([sys.executable,'-c',command],check=True)
  # Remove only the superseded user-facing Markdown folder, not provenance.
  old=base/'results/gemini/mandol_100_20'
  if old.exists():
   assert set(p.name for p in old.iterdir()) <= {'README.md','latency.md','retrieval.md'}
   shutil.rmtree(old)
  print(case,'merged into canonical reports;',expected,'D20 answers',flush=True)
if __name__=='__main__':main()
