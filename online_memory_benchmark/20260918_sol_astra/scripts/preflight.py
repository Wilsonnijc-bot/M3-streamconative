"""Fail-closed artifact, dependency, model, media, and device verification."""
import importlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import urllib.request
from bench_common import ROOT, REVISION, atomic, read, rows, sha, digest


def validate_tst(dataset):
    cfg=read(ROOT/'configs'/f'tst_{dataset}.json')
    assert cfg['enrollment_policy']=='online_native_m3' and cfg['pre_enrollment'] is False
    assert cfg['excluded_intervals']==[]
    assert cfg['encoder']['model']=='speechbrain/spkrec-ecapa-voxceleb' and cfg['encoder']['revision']==REVISION
    assert cfg['threshold']==read(ROOT/'configs/memory_config.json')['audio_matching_threshold']
    assert cfg['max_audio_embeddings']==read(ROOT/'configs/memory_config.json')['max_audio_embeddings']
    expected=dict(cfg);method=expected.pop('method_id');assert digest(expected)==method
    encoder=read(ROOT/cfg['encoder_provenance']);assert encoder['fingerprint']==cfg['encoder_fingerprint']
    snapshot=ROOT/'tst_assets/huggingface/hub/models--speechbrain--spkrec-ecapa-voxceleb/snapshots'/REVISION
    for name,h in encoder['asset_hashes'].items():assert sha(snapshot/name)==h
    return dict(policy=cfg['enrollment_policy'],pre_enrollment=False,threshold=cfg['threshold'],method_id=method,encoder_revision=REVISION)


def main():
    from runtime_support import environment
    environment()
    checks={};failures=[]
    def check(name,fn):
        try:checks[name]=fn()
        except Exception as e:failures.append(name+': '+type(e).__name__+': '+str(e))
    import torch
    def cuda():
        assert torch.cuda.is_available() and torch.arange(8,device='cuda').square().sum().item()==140
        return dict(gpu=torch.cuda.get_device_name(0),torch=torch.__version__)
    check('cuda',cuda)
    for module in ('speechbrain','m3_agent.memorization_memory_graphs','mmagent.tst_mapper','mmagent.retrieve','streammeco','consolidation.runtime_io','consolidation.llm_consolidator'):
        check('import:'+module,lambda module=module:bool(importlib.import_module(module)))
    for dataset in ('jake','aea'):
        check('tst:'+dataset,lambda dataset=dataset:validate_tst(dataset))
        def media(dataset=dataset):
            from event_plan import make_plan
            from online_benchmark import dataset_plan
            manifest=read(ROOT/'configs/media'/f'{dataset}.json')
            for r in manifest['recordings']:
                p=Path(r['path']);assert p.is_file() and p.stat().st_size==r['bytes']
                assert sha(p)==r['sha256'], r['source_id']
            plan=dataset_plan(dataset)
            expected=102 if dataset=='jake' else 1000
            assert sum(len(e['questions']) for e in plan)==expected
            normalized=read(ROOT/'configs'/f'{dataset}_questions.json')
            if dataset=='jake':
                import csv
                from build_question_manifests import clock_seconds
                source=ROOT/'assets/questions/egolifeqa_benchmark.csv'
                originals={r['question_id']:r for r in csv.DictReader(source.open()) if r['query_time_raw'].startswith('DAY1@')}
                assert set(originals)=={q['question_id'] for q in normalized['questions']}
                for q in normalized['questions']:
                    original=originals[q['question_id']]
                    assert q['question']==original['question'] and q['ground_truth']==chr(65+int(original['answer_index']))
                    assert list(q['options'].values())==json.loads(original['choices'])
                    assert q['query_timestamp']==clock_seconds(original['query_time_raw'].split('@')[1])
                    assert q['source_annotation']['sha256']==sha(source)
            else:
                source=ROOT/'assets/questions/aea_all_questions.json'
                assert normalized['selection']['source_sha256']==sha(source)
                ordered=sorted(read(source)['questions'],key=lambda q:(q['query_timestamp'],q['question_id']))
                indices=[(i*(len(ordered)-1))//999 for i in range(1000)]
                assert normalized['selection']['selected_indices']==indices
                assert normalized['questions']==[ordered[i] for i in indices]

            for e in plan:
                for gap in read(ROOT/'configs'/f'tst_{dataset}.json')['excluded_intervals']:
                    if max(e['start_s'],gap['start_s'])<min(e['end_s'],gap['end_s']):assert e['gap']=='held_out_tst'
            return dict(recordings=len(manifest['recordings']),events=len(plan),questions=expected,plan_hash=digest(plan),duration_s=plan[-1]['end_s'])
        check('media:'+dataset,media)
    def models():
        for model in ('gpt-5.6-terra','gpt-5.6-sol'):
            req=urllib.request.Request('https://api.openai.com/v1/models/'+model,headers={'Authorization':'Bearer '+os.environ['OPENAI_API_KEY']})
            with urllib.request.urlopen(req,timeout=30) as r:assert json.load(r)['id']==model
        return ['gpt-5.6-terra','gpt-5.6-sol']
    check('official_model_access',models)
    def shared_consolidation():
        import consolidation.port
        actual=Path(consolidation.port.__file__).resolve()
        expected=ROOT.parents[1]/'consolidation/port.py'
        assert actual==expected.resolve(), 'benchmark must import shared consolidation'
        assert (ROOT/'source/consolidation').is_symlink()
        return str(actual)
    check('shared_consolidation',shared_consolidation)
    def moss_config():
        cfg=read(ROOT/'configs/moss.json')
        assert cfg['backend']=='local' and (Path(cfg['checkpoint'])/'config.json').is_file()
        revision=subprocess.check_output(['git','-C',cfg['repository'],'rev-parse','HEAD'],text=True).strip()
        assert revision==cfg['repository_revision']
        env=dict(os.environ,PYTHONPATH=cfg['repository']+os.pathsep+os.environ.get('PYTHONPATH',''))
        subprocess.run([sys.executable,'-c','from moss_transcribe_diarize.inference_utils import generate_transcription'],env=env,check=True)
        return dict(configured=True,revision=cfg['revision'],repository_revision=revision)
    check('moss_window_runner',moss_config)
    def embedding_access():
        from mmagent.utils.chat_api import get_embeddings_batch
        vectors,_=get_embeddings_batch('text-embedding-3-large',['benchmark preflight'])
        assert len(vectors)==1 and len(vectors[0])>0
        return dict(status='ready',dimensions=len(vectors[0]))
    check('official_embedding_quota',embedding_access)
    def checkpoints():
        manifest=read(ROOT/'configs/model_manifest.json')
        for name,r in manifest['files'].items():
            p=Path(name);assert p.stat().st_size==r['bytes'] and sha(p)==r['sha256'],name
        return len(manifest['files'])
    check('local_model_hashes',checkpoints)
    for key in ('OPENAI_API_KEY','DEEPGRAM_API_KEY','API_302_KEY'):
        check('credential_present:'+key,lambda key=key:True if os.environ.get(key) else (_ for _ in ()).throw(ValueError('missing')))
    def disk():
        free=shutil.disk_usage(ROOT).free
        assert free>=4*1024**3,'Need at least 4 GiB before full run'
        return free
    check('disk_free_bytes',disk)
    def mandol():
        result=subprocess.run(['/opt/streammeco/mandol-venv/bin/python','-c',
            'from mandol.adapters.m3.adapter import M3MandolAdapter; from mandol.adapters.m3.retriever import M3MandolRetriever; from mandol.utils.model_manager import global_model_manager; assert global_model_manager.get_splade_model() is not None; print("MANDOL_IMPORT_OK")'],cwd=ROOT/'mandol_runtime',capture_output=True,text=True)
        (ROOT/'logs/mandol_preflight.log').write_text(result.stdout+result.stderr)
        assert result.returncode==0,'See logs/mandol_preflight.log'
        return True
    check('mandol',mandol)
    def reranking_config():
        cfg=read(ROOT/'configs/mandol.json')['reranking']
        assert cfg['method']=='qwen-302' and cfg['endpoint']=='https://api.302.ai/v1/rerank'
        return cfg
    check('reranking_config',reranking_config)
    report=dict(status='ready' if not failures else 'blocked',checks=checks,blockers=failures,benchmark_started=False,instance_id='1042997')
    atomic(ROOT/'metadata/readiness.json',report);print(json.dumps(report,indent=2));sys.exit(2 if failures else 0)

if __name__=='__main__':main()
