"""Runtime environment, frozen-prefix evidence, and measured consolidation adapter."""
import json
import os
from pathlib import Path
import sys
from bench_common import ROOT, PRODUCTION_ROOTS, production_pythonpath, read, atomic, append


def environment():
    os.chdir(ROOT)
    os.environ['M3_MEMORY_BACKEND']=read(ROOT/'configs/processing_config.json')['memory_backend']
    os.environ['M3_MEMORY_ARTIFACTS']=str(ROOT/'cache/terra_construction')
    for p in reversed(production_pythonpath()):
        sys.path.insert(0,str(p))
    os.environ['HF_HOME']=str(ROOT/'tst_assets/huggingface')
    os.environ['CAMPLUS_CHECKPOINT']='/opt/streammeco/models/camplus/v1.0.0/campplus_cn_en_common.pt'
    os.environ['INSIGHTFACE_MODEL_ROOT']='/opt/streammeco/models/insightface'
    os.environ['PYTHONHASHSEED']='0'
    os.environ['TMPDIR']=str(ROOT/'tmp');Path(os.environ['TMPDIR']).mkdir(exist_ok=True)
    # Import credentials from the existing deployment into process memory only.
    private=PRODUCTION_ROOTS['StreamMeCo']/'configs/api_config.json'
    if private.exists():
        for item in read(private).values():
            if item.get('api_key_env') and item.get('api_key'):
                os.environ.setdefault(item['api_key_env'],item['api_key'])
    os.environ['PYTHONPATH']=os.pathsep.join(map(str,production_pythonpath()))
    mandol_dir=ROOT/'mandol_runtime';mandol_dir.mkdir(exist_ok=True)
    if not (mandol_dir/'naver').exists():(mandol_dir/'naver').symlink_to(PRODUCTION_ROOTS['Mandol']/'naver',target_is_directory=True)
    os.environ.pop('EGOLIFE_GEMINI_ONLY',None)
    os.environ.pop('EGOLIFE_RESULTS',None)  # ASR must fail closed.


def collect_evidence(snapshot, directory, session, plan):
    from mmagent.consolidation_evidence import export_consolidation_evidence

    return export_consolidation_evidence(snapshot, directory, session, plan)

def attach(graph,directory,session,plan,*,moss=None):
    from consolidation.port import attach_online
    def evidence(snapshot):
        return collect_evidence(snapshot,directory,session,plan)
    return attach_online(graph,evidence,directory/'consolidation',
        api_config=ROOT/'configs/official_consolidation.json',
        model=read(ROOT/'configs/run_request.json')['consolidation_backend']['model'],
        moss=moss,moss_config=read(ROOT/'configs/moss.json'),period_s=1200)


def barrier(runtime,cutoff,directory):
    result=runtime.consolidate_until(cutoff,progress=lambda t,elapsed:
        print('CONSOLIDATION_WAIT',t,'elapsed_s',round(elapsed,1),flush=True))
    result['job_directory']=str(Path(result['job_directory']).relative_to(ROOT))
    append(directory/'consolidation.jsonl',result)
    atomic(directory/'consolidation'/f'event_{cutoff:012.6f}.json',result)
    if cutoff<=3600:
        path=directory/'consolidation'/f'event_{int(cutoff):04d}.md'
        path.write_text(f'# Consolidation at {cutoff:g} media seconds\n\nDetailed snapshot, evidence, official request/response, accepted/rejected decisions, and native identity changes are in snapshot job directories.\n\n```json\n'+json.dumps(result,ensure_ascii=False,indent=2)+'\n```\n')
    return result
