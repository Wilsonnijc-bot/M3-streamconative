"""Promote a validated D100/20 rerun into a benchmark's canonical A/B/C/D results."""
import argparse,hashlib,importlib.util,json,shutil,time
from pathlib import Path
from types import SimpleNamespace

FILES=['method_D_mandol.jsonl','aggregate_metrics.json','comparison.csv','comparison.md',
       'detailed_retrieval_events.jsonl','detailed_latency_events.jsonl','gemini_calls.jsonl',
       'retrieval_warmup.jsonl','validation.json','snapshot_provenance.json']
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def rows(path):return [json.loads(l) for l in path.read_text().splitlines() if l.strip()] if path.exists() else []
def write(path,value):
 temp=path.with_suffix(path.suffix+'.tmp');temp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n');temp.replace(path)
def write_rows(path,data):
 temp=path.with_suffix(path.suffix+'.tmp');temp.write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in data));temp.replace(path)
def promote(run,report_module):
 root=run/'results';variant=run/'reruns/mandol_100_20';source=variant/'results';validation=json.loads((source/'validation.json').read_text())
 assert validation['status']=='complete' and not validation['problems']
 assert validation['source_graphs_unchanged'] and validation['baseline_unchanged']
 new=source/'method_D_mandol.jsonl';old=variant/'baseline_method_D_2nodes.jsonl';selected=root/'method_D_mandol.jsonl'
 assert digest(selected) in {digest(old),digest(new)},'Unexpected canonical D results; refusing overwrite'
 data=rows(new);assert len(data)==validation['qa_rows']
 assert all(x['top_k']==20 and len(x['retrieved_evidence'])==20 for x in data)
 before={p.name:digest(p) for p in root.glob('method_[ABC]_*.jsonl')}
 archive=variant/'provenance/canonical_before_promotion';archive.mkdir(parents=True,exist_ok=True)
 for name in FILES:
  p=root/name
  if p.exists() and not (archive/name).exists():shutil.copy2(p,archive/name)
 shutil.copy2(new,selected)
 # Rebuild selected telemetry from its immutable pre-promotion version, so repeat
 # promotion never duplicates rerun calls. Historical logs remain in provenance.
 for name in ['gemini_calls.jsonl','detailed_latency_events.jsonl','retrieval_warmup.jsonl']:
  base=rows(archive/name)
  if name=='detailed_latency_events.jsonl':
   keep=[x for x in base if x.get('method')!='D' or x.get('event')=='adaptor']
  else:keep=[x for x in base if x.get('method')!='D']
  write_rows(root/name,keep+rows(source/name))
 config=json.loads((variant/'config.json').read_text())
 selection={'method':'D','candidate_pool':100,'final_results':20,'provider':'302.ai',
            'source':'../reruns/mandol_100_20/results/method_D_mandol.jsonl',
            'source_sha256':digest(new),'baseline_sha256':digest(old),
            'baseline':'../reruns/mandol_100_20/baseline_method_D_2nodes.jsonl',
            'grading_source':'../reruns/mandol_100_20/results/grading' if config['dataset']=='bedroom' else 'exact multiple-choice scoring',
            'timing_note':'D is the later 100-candidate/20-node rerun. A/B/C retain their original measurements; execution periods differ. No timings were recomputed.',
            'actual_candidate_counts':validation['actual_candidate_counts'],'promoted_at':time.time()}
 write(root/'method_D_selection.json',selection)
 spec=importlib.util.spec_from_file_location('canonical_report',report_module);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 module.report(SimpleNamespace(results=root));module.validate(SimpleNamespace(results=root))
 assert all(digest(root/name)==expected for name,expected in before.items())
 write(variant/'promotion.json',{'status':'complete','canonical_results':str(root),'ABC_unchanged':True,'method_D_selection':selection})
 print('PROMOTED_D100_20',run,flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--report-module',type=Path,required=True);a=p.parse_args();promote(a.run,a.report_module)
