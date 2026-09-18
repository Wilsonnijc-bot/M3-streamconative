"""Deterministic online C1-C4 construction and one-shot R1/R2 evaluation."""
import argparse
import base64
from collections import Counter
import copy
import hashlib
import json
import os
from pathlib import Path
import pickle
import re
import random
import shutil
import subprocess
import sys
import tempfile
import time
from bench_common import ROOT, atomic, read, rows, sha, digest, append
from event_plan import make_plan, maintenance_actions

METHODS={'C1':('CAM++',.5,False),'C2':('TST',.5,False),'C3':('TST',.5,True),'C4':('TST',.7,True)}


def source_fingerprint():
    paths=[]
    for base in (ROOT/'configs',ROOT/'scripts',ROOT/'source'):
        paths += [p for p in base.rglob('*') if p.is_file() and p.suffix in ('.py','.json','.sh','.md','.yaml') and '__pycache__' not in str(p)]
    shared=ROOT/'source/consolidation'
    paths += [p for p in shared.rglob('*') if p.is_file() and p.suffix in ('.py','.json','.md')
              and not any(part in ('runs','.venv','__pycache__','tests') for part in p.relative_to(shared).parts)]
    return {str(p.relative_to(ROOT)):sha(p) for p in sorted(paths)}


def dataset_plan(dataset):
    manifest=read(ROOT/'configs/media'/f'{dataset}.json')
    questions=read(ROOT/'configs'/f'{dataset}_questions.json')['questions']
    questions=[dict(q,media_timestamp=round(q['query_timestamp']-manifest['origin_s'],6)) for q in questions]
    tst=read(ROOT/'configs'/f'tst_{dataset}.json')
    plan=make_plan(manifest['recordings'],questions,tst['excluded_intervals'])
    plan[-1]['consolidate']=True
    return plan


def graph_bytes(graph):return pickle.dumps(graph,protocol=pickle.HIGHEST_PROTOCOL)

def periodic_graph_path(folder,method,cutoff):
    return folder/method/'graph_snapshots'/f't_{cutoff:012.6f}'/'graph.pkl'


def checkpoint(folder,graphs,index,fingerprint,plan_hash,phase="complete",media_timestamp=None):
    periodic=media_timestamp is not None and round(media_timestamp*1e6)%300000000==0 and phase!='observations_committed'
    generation=folder/'transactions'/f'event_{index:06d}_{phase}'
    files={}
    for method,graph in graphs.items():
        path=periodic_graph_path(folder,method,media_timestamp) if periodic else generation/method/'pending.pkl'
        payload=graph_bytes(graph);expected=hashlib.sha256(payload).hexdigest()
        if path.exists():
            if sha(path)!=expected:raise ValueError('checkpoint state changed within a timestamp')
        else:atomic(path,payload,True)
        files[method]=dict(path=str(path.relative_to(folder)),sha256=expected)
    old=read(folder/'CURRENT.json') if (folder/'CURRENT.json').exists() else None
    atomic(folder/'CURRENT.json',dict(event_index=index,phase=phase,media_timestamp=media_timestamp,periodic=periodic,
        generation=None if periodic else str(generation.relative_to(folder)),fingerprint=fingerprint,plan_hash=plan_hash,graphs=files))
    # Temporary transaction state survives a crash, then expires at the next
    # published checkpoint. Five-minute snapshots remain permanent.
    if old and not old.get('periodic',False) and old.get('generation') and old['generation']!=str(generation.relative_to(folder)):
        previous=folder/old['generation']
        if previous.is_dir():shutil.rmtree(previous)


def finish_transaction(folder,index):
    if not (folder/'CURRENT.json').exists():return
    state=read(folder/'CURRENT.json')
    if state['event_index']==index:
        state['phase']='complete';atomic(folder/'CURRENT.json',state)


def resume(folder,fingerprint,plan_hash):
    state=read(folder/'CURRENT.json')
    if state['fingerprint']!=fingerprint or state['plan_hash']!=plan_hash:raise ValueError('resume refused: config/model/source/manifest mismatch')
    graphs={}
    for method,item in state['graphs'].items():
        p=folder/item['path']
        if sha(p)!=item['sha256']:raise ValueError('checkpoint hash mismatch')
        graphs[method]=pickle.loads(p.read_bytes())
    if set(graphs)!=set(METHODS):raise ValueError('incomplete C1-C4 checkpoint')
    return graphs,state['event_index']


def freeze(graph,path,cutoff):
    for node in graph.nodes.values():
        if node.type in ('episodic','semantic'):
            if graph.segment_times[node.metadata['timestamp']][1]>cutoff:raise ValueError('future memory in snapshot')
    payload=graph_bytes(graph);hash_=hashlib.sha256(payload).hexdigest()
    if path.exists() and path.read_bytes()!=payload:raise ValueError('snapshot changed on resume')
    atomic(path,payload,True);return hash_


class MandolWorker:
    def __init__(self,folder):
        self.log=(folder/'mandol_worker.log').open('a')
        self.proc=subprocess.Popen(['/opt/streammeco/mandol-venv/bin/python','-u',str(ROOT/'scripts/mandol_snapshot.py'),'--snapshot',str(folder),'--serve'],
            cwd=ROOT/'mandol_runtime',stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=self.log,text=True,bufsize=1)
        self.wait('BENCH_READY')
    def wait(self,prefix):
        for line in self.proc.stdout:
            self.log.write(line);self.log.flush()
            if line.startswith(prefix):return line.strip()
        self.proc.wait(timeout=10)
        raise RuntimeError('Mandol worker stopped: '+str(self.proc.returncode))
    def search(self,q):
        self.proc.stdin.write(json.dumps(q)+'\n');self.proc.stdin.flush()
        return read(self.wait('BENCH_RESULT ').split(' ',1)[1])
    def close(self):
        if self.proc.poll() is None:
            self.proc.stdin.write('{"stop":true}\n');self.proc.stdin.flush();self.proc.stdin.close()
            self.proc.wait(timeout=120)
        self.log.close()
        if self.proc.returncode:raise RuntimeError('Mandol worker failed')


def queries(graph,event,directory,dataset,method):
    from mmagent.retrieve import search
    from m3_agent.export_mandol import export_graph
    from answer_stream import answer
    folder=directory/'snapshots'/f"t_{event['end_s']:012.6f}";folder.mkdir(parents=True,exist_ok=True)
    validation=any(q.get('diagnostic_only') for q in event['questions'])
    snapshot=folder/('validation_graph.pkl' if validation else 'qa_state.tmp.pkl');hash_=freeze(graph,snapshot,event['end_s'])
    atomic(folder/'snapshot.json',dict(sha256=hash_,media_timestamp=event['end_s'],maintenance_before_qa=True,temporary_graph=not validation))
    qs=event['questions']
    if (folder/'mandol_request.json').exists():
        existing=read(folder/'mandol_request.json')
        if existing['snapshot_sha256']!=hash_ or existing['questions']!=qs:raise ValueError('Mandol request resume mismatch')
    else:
        export_started=time.perf_counter()
        export_graph(snapshot,folder/'export',video_id=f'{dataset}_{method}',clip_duration_seconds=30,compressed=event['end_s']>=3600)
        export_ms=(time.perf_counter()-export_started)*1000
        atomic(folder/'mandol_request.json',dict(snapshot_sha256=hash_,questions=qs,export_ms=export_ms))
    worker=MandolWorker(folder)
    try:
        for q in qs:
            for path in ('R1','R2'):
                output=folder/'answers'/q['question_id']/path
                result_path=output/'result.json'
                if result_path.exists():
                    if read(result_path)['snapshot_sha256']!=hash_:raise ValueError('QA resume snapshot mismatch')
                    continue
                output.mkdir(parents=True,exist_ok=True)
                question_wall=time.time();question_perf=time.perf_counter()
                retrieval_path=output/'retrieval.json'
                if retrieval_path.exists():
                    retrieval=read(retrieval_path);evidence=retrieval['evidence']
                    question_wall=retrieval['question_start_ts']
                else:
                    t=time.perf_counter()
                    if path=='R1':
                        query_graph=pickle.loads(snapshot.read_bytes());metrics={}
                        evidence,_,_=search(query_graph,q['question'],[],topk=10,metrics=metrics)
                        retrieval=dict(evidence=evidence,metrics=metrics,retrieval_calls=1,retrieval_ms=(time.perf_counter()-t)*1000,snapshot_sha256=hash_)
                    else:
                        retrieval=worker.search(q);evidence=retrieval['evidence']
                    retrieval['question_start_ts']=question_wall
                    atomic(retrieval_path,retrieval)
                if retrieval['snapshot_sha256']!=hash_:raise ValueError('R1/R2 snapshot mismatch')
                response=answer(q,evidence,output)
                letter=re.match(r'^\s*([A-E])\b',response['answer'])
                result=dict(dataset=dataset,construction_method=method,retrieval_method=path,question=q,
                    benchmark_timestamp=event['end_s'],snapshot_sha256=hash_,snapshot=str(snapshot.relative_to(ROOT)),
                    retrieval=retrieval,answer=response,correct=bool(letter and letter.group(1)==q['ground_truth']),
                    evaluator='leading option letter exact match; missing letter is incorrect',
                    question_to_first_token_ms=(response['first_content_token_ts']-question_wall)*1000,
                    question_to_complete_answer_ms=(response['response_end_ts']-question_wall)*1000,
                    answer_calls=1,retrieval_calls=1)
                atomic(result_path,result);append(directory/'qa.jsonl',result)
                print('QA_COMPLETE',dataset,method,q['question_id'],path,'TTFT',round(response['ttft_ms'],1),flush=True)
        if sha(snapshot)!=hash_:raise ValueError('immutable snapshot was modified')
    finally:worker.close()
    if not validation:snapshot.unlink()


def hourly(graph,event,directory,dataset,method,compression):
    from reports import write_hour
    folder=directory/f"hour_{int(event['end_s']//3600):02d}";folder.mkdir(exist_ok=True)
    target=periodic_graph_path(directory.parent,method,event['end_s'])
    if not target.exists():atomic(target,graph_bytes(graph),True)
    link=folder/'graph.pkl'
    if not link.exists():link.symlink_to(os.path.relpath(target,folder))
    atomic(folder/'state.json',dict(dataset=dataset,method=method,media_timestamp=event['end_s'],compression=compression,
        graph_sha256=sha(folder/'graph.pkl'),consolidation_watermark=getattr(graph,'last_consolidated_timestamp',None)))
    write_hour(graph,event,directory,folder,dataset,method,compression)


def run_dataset(dataset,results,do_resume=False,max_events=None,smoke=False):
    from mmagent.videograph import VideoGraph
    from mmagent.tst_mapper import TSTVoiceMapper
    from mmagent.utils.video_processing import process_video_clip
    from mmagent.utils.chat_api import transcribe_audio_with_retry
    from mmagent.utils.asr_selection import run_selected_asr
    from m3_agent.memorization_memory_graphs import process_segment
    from streammeco import compress_graph
    from runtime_support import attach,barrier
    plan=dataset_plan(dataset);plan_hash=digest(plan)
    fingerprint=digest(source_fingerprint());folder=results/dataset;folder.mkdir(parents=True,exist_ok=True)
    atomic(folder/'event_plan.json',plan);atomic(folder/'source_hashes.json',source_fingerprint())
    if (folder/'CURRENT.json').exists():
        if not do_resume:raise ValueError('existing checkpoint; pass --resume')
        graphs,start_index=resume(folder,fingerprint,plan_hash)
        resume_phase=read(folder/'CURRENT.json').get('phase','complete')
    else:
        graphs={m:VideoGraph(**read(ROOT/'configs/memory_config.json')) for m in METHODS};start_index=0
        for g in graphs.values():g.segment_times={}
        resume_phase='complete'
    assert len({id(g) for g in graphs.values()})==4
    mapper=TSTVoiceMapper(ROOT,ROOT/'configs'/f'tst_{dataset}.json')
    runtimes={}
    for method,graph in graphs.items():
        d=folder/method;d.mkdir(exist_ok=True)
        if method!='C1':graph.speaker_mapper=mapper
        if METHODS[method][2]:runtimes[method]=attach(graph,d,f'{dataset}/{method}',plan)
    cache=ROOT/'cache'/dataset;cache.mkdir(parents=True,exist_ok=True)
    try:
        for index,event in enumerate(plan,1):
            if index<start_index or (index==start_index and resume_phase=='complete'):continue
            if index==start_index and resume_phase=='state_ready':
                for method,graph in graphs.items():
                    if event['questions']:queries(graph,event,folder/method,dataset,method)
                    if event['compress']:
                        compression=read(folder/method/f"hour_{int(event['end_s']//3600):02d}/state.json")['compression']
                        hourly(graph,event,folder/method,dataset,method,compression)
                finish_transaction(folder,index)
                print('EVENT_RESUMED',dataset,index,flush=True)
                continue
            if max_events is not None and index>max_events:break
            if shutil.disk_usage(ROOT).free<1024**3:raise RuntimeError('disk guard: less than 1 GiB free')
            print('EVENT_START',dataset,index,event['start_s'],event['end_s'],event['gap'],flush=True)
            event_started=time.perf_counter();temporary_peak=0
            replay_committed=index==start_index and resume_phase=='observations_committed'
            with tempfile.TemporaryDirectory(prefix=f'{dataset}_{index}_',dir=ROOT/'tmp') as temporary:
                if not event['gap'] and not replay_committed:
                    media=Path(temporary)/'segment.mp4';source=event['source'];length=event['end_s']-event['start_s']
                    offset=source['source_offset_s']+event['start_s']-source['start_s']
                    t=time.perf_counter()
                    # Re-encode exact interval; no keyframe seek extension into the future.
                    subprocess.run(['ffmpeg','-v','error','-y','-ss',f'{offset:.6f}','-i',source['path'],'-t',f'{length:.6f}',
                        '-map','0:v:0','-map','0:a:0?','-vf','scale=640:-2','-c:v','libx264','-preset','ultrafast','-crf','25','-c:a','aac',str(media)],check=True)
                    temporary_peak=media.stat().st_size
                    video,frames,audio=process_video_clip(media,fps=read(ROOT/'configs/processing_config.json')['fps'],audio_duration_limit=length)
                    decode_ms=(time.perf_counter()-t)*1000
                    asr_key=digest(dict(audio_sha256=hashlib.sha256(base64.b64decode(audio)).hexdigest() if audio else None,provider=read(ROOT/'configs/api_config.json')['deepgram-asr']))
                    asr_path=cache/'asr'/f'{asr_key}.json'
                    asr_cache_hit=asr_path.exists();asr_lookup_started=time.perf_counter()
                    if asr_cache_hit:
                        stored=read(asr_path)
                        prepared=(stored[0],stored[1],{'deepgram-asr':None},None) if stored else None
                    else:
                        prepared=run_selected_asr('deepgram-asr',lambda name:transcribe_audio_with_retry(name,base64.b64decode(audio),audio_format='wav')) if audio else None
                        atomic(asr_path,prepared)
                    asr_context=dict(cache_hit=asr_cache_hit,cache_path=str(asr_path.relative_to(ROOT)),lookup_or_request_ms=(time.perf_counter()-asr_lookup_started)*1000,timing_scope='shared event ASR; cached request duration not reported as new inference')
                    if audio and ('deepgram-asr' not in prepared[0] or prepared[1]):raise RuntimeError('selected ASR failed')
                for method,graph in graphs.items():
                    if replay_committed:continue
                    directory=folder/method
                    import numpy as np, torch
                    seed=int(digest([dataset,index])[:8],16)
                    random.seed(seed);np.random.seed(seed);torch.manual_seed(seed);torch.cuda.manual_seed_all(seed)
                    graph.segment_times[index]=(event['start_s'],event['end_s'])
                    if event['gap']:
                        if method in runtimes:
                            with runtimes[method].segment(index,event['end_s']):pass
                        audit=dict(clip_id=index,gap=event['gap'],voice_observations=[],latency_ms={})
                    else:
                        sample=dict(intermediate_outputs=str(directory/'intermediate'),clip_audit_dir=str(directory/'audits'),
                            segment_end_s=event['end_s'],prepared_asr=prepared,asr_context=asr_context,persist_clip_graphs=False)
                        t=time.perf_counter();construction_queue_ms=(t-event_started)*1000
                        audit=process_segment(graph,video,frames,audio,index,sample,str(media),metrics={'clip_decode_ms':decode_ms})
                        audit['admission_to_commit_ms']=(time.perf_counter()-t)*1000
                        audit['construction_queue_including_shared_preprocessing_ms']=construction_queue_ms
                        if audit['stage_details']['voice']['speaker_mapping']!=METHODS[method][0]:raise ValueError('wrong speaker mapper')
                    append(directory/'construction.jsonl',dict(dataset=dataset,construction_method=method,benchmark_timestamp=event['end_s'],wall_clock_timestamp=time.time(),**audit))
                if not event['gap'] and not replay_committed:
                    media.unlink()
                    del video,frames,audio,prepared
                # Quiesce background native indexing before checkpoint/snapshot copies.
                for runtime in runtimes.values():
                    with runtime.condition:
                        while runtime.index_job is not None:runtime.condition.wait(timeout=30)
                        if runtime.errors:raise RuntimeError(repr(runtime.errors))
                if event['consolidate'] or event['compress'] or event['questions']:
                    checkpoint(folder,graphs,index,fingerprint,plan_hash,phase='observations_committed',media_timestamp=event['end_s'])
                if replay_committed and event['consolidate']:
                    for runtime in runtimes.values():
                        runtime.pending=runtime.graph.last_consolidated_timestamp<event['end_s']
                # All four construction commits precede timestamp maintenance and QA.
                compressions={};saved_ready=False
                for action,method in maintenance_actions(event):
                    graph=graphs[method];directory=folder/method
                    if action=='consolidate':barrier(runtimes[method],event['end_s'],directory)
                    elif action=='compress':
                        before=sum(n.type in ('episodic','semantic') for n in graph.nodes.values())
                        graph,summary=compress_graph(graph,retain_ratio=METHODS[method][1])
                        after=sum(n.type in ('episodic','semantic') for n in graph.nodes.values())
                        compression=dict(requested_ratio=METHODS[method][1],before=before,after=after,removed=before-after,actual_retention=after/before if before else None,summary=summary)
                        append(directory/'compression.jsonl',dict(media_timestamp=event['end_s'],**compression))
                        compressions[method]=compression
                    elif action=='persist':hourly(graph,event,directory,dataset,method,compressions[method])
                    elif action=='qa':
                        if not saved_ready:
                            checkpoint(folder,graphs,index,fingerprint,plan_hash,phase='state_ready',media_timestamp=event['end_s'])
                            saved_ready=True
                        queries(graph,event,directory,dataset,method)
                        if event['compress']:hourly(graph,event,directory,dataset,method,compressions[method])
            if Path(temporary).exists():raise RuntimeError('temporary media cleanup failed')
            append(folder/'events.jsonl',dict(event_index=index,media_timestamp=event['end_s'],temporary_peak_bytes=temporary_peak,temporary_removed=True,resumed_observations=replay_committed,
                wall_ms=(time.perf_counter()-event_started)*1000,status='committed',event_order=['observations','consolidation','compression','hourly_state','qa']))
            if event['snapshot_due']:
                checkpoint(folder,graphs,index,fingerprint,plan_hash,media_timestamp=event['end_s'])
            elif smoke or index==len(plan):
                checkpoint(folder,graphs,index,fingerprint,plan_hash,phase='complete',media_timestamp=event['end_s'])
            else:finish_transaction(folder,index)
            print('EVENT_COMMITTED',dataset,index,event['end_s'],flush=True)
        if smoke:
            # Diagnostic calls explicitly use the prefix cutoff and are separate from benchmark QA.
            event=copy.deepcopy(plan[min(max_events or 1,len(plan))-1])
            original=read(ROOT/'configs'/f'{dataset}_questions.json')['questions'][0]
            event['questions']=[dict(original,question_id='smoke_'+original['question_id'],query_timestamp=event['end_s'],diagnostic_only=True,original_query_timestamp=original['query_timestamp'])]
            for method,graph in graphs.items():queries(graph,event,folder/method,dataset,method)
            atomic(folder/'SMOKE_PASS.json',dict(status='passed',media_cutoff=event['end_s'],methods=list(METHODS),paths=['R1','R2'],diagnostic_qa=True))
    finally:
        for runtime in runtimes.values():
            runtime.close(flush_final=False)


def main():
    p=argparse.ArgumentParser();p.add_argument('--run-root',type=Path,default=ROOT);p.add_argument('--request');p.add_argument('--jake-questions');p.add_argument('--aea-questions')
    p.add_argument('--results',type=Path,default=ROOT/'results');p.add_argument('--dataset',choices=['jake','aea','both'],default='both');p.add_argument('--resume',action='store_true');p.add_argument('--max-events',type=int);p.add_argument('--smoke',action='store_true');p.add_argument('--validate-prefix',action='store_true')
    a=p.parse_args()
    a.results=a.results.resolve()
    if not a.results.is_relative_to(ROOT):raise ValueError('results must remain inside isolated benchmark folder')
    if a.run_root.resolve()!=ROOT:raise ValueError('run root differs from isolated source location')
    request=read(ROOT/'configs/run_request.json')
    assert request['primary_backend']['model_id']=='gpt-5.6-terra' and request['primary_backend']['reasoning_effort']=='medium'
    assert request['consolidation_backend']['model']=='gpt-5.6-sol' and request['consolidation_backend']['reasoning_effort']=='high'
    for method,(speaker,ratio,consolidates) in METHODS.items():
        expected=request['construction'][method]
        assert expected['speaker']==speaker and expected['retain_ratio']==ratio
        assert expected.get('consolidation_interval_s',0)==(1200 if consolidates else 0)
    assert request['compression_interval_s']==3600 and request['graph_snapshot_interval_s']==300
    if a.validate_prefix:
        import unittest
        result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.discover(str(ROOT/'tests')))
        atomic(ROOT/'metadata/prefix_static.json',dict(passed=result.wasSuccessful(),tests=result.testsRun,skipped=len(result.skipped),failures=len(result.failures),errors=len(result.errors)));sys.exit(not result.wasSuccessful())
    from runtime_support import environment
    environment()
    import fcntl
    a.results.mkdir(parents=True,exist_ok=True)
    writer_lock=(a.results/'WRITER.lock').open('a')
    fcntl.flock(writer_lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    for dataset in ('jake','aea') if a.dataset=='both' else (a.dataset,):run_dataset(dataset,a.results,a.resume,a.max_events,a.smoke)
    if not a.max_events:atomic(a.results/'COMPLETE.json',dict(status='completed',datasets=['jake','aea'] if a.dataset=='both' else [a.dataset]))
    print('BENCHMARK_COMPLETED' if not a.max_events else 'PREFIX_COMPLETED',flush=True)

if __name__=='__main__':main()
