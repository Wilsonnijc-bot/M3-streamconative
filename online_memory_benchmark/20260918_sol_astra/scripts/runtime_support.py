"""Runtime environment, frozen-prefix evidence, and measured consolidation adapter."""
import json
import os
from pathlib import Path
import sys
import time
from bench_common import ROOT, read, atomic, append


def environment():
    os.chdir(ROOT)
    for p in (ROOT/'source', ROOT/'source/StreamMeCo',Path('/opt/streammeco/repos/3D-Speaker')):
        sys.path.insert(0,str(p))
    os.environ['HF_HOME']=str(ROOT/'tst_assets/huggingface')
    os.environ['CAMPLUS_CHECKPOINT']='/opt/streammeco/models/camplus/v1.0.0/campplus_cn_en_common.pt'
    os.environ['INSIGHTFACE_MODEL_ROOT']='/opt/streammeco/models/insightface'
    os.environ['QWEN_MODEL_PATH']='/opt/streammeco/models/Qwen3.5-4B'
    processing=read(ROOT/'configs/processing_config.json')
    os.environ['QWEN_MEMORY_ENABLE_THINKING']=str(processing['qwen_enable_thinking']).lower()
    os.environ['QWEN_MEMORY_MAX_NEW_TOKENS']=str(processing['qwen_thinking_max_new_tokens'] if processing['qwen_enable_thinking'] else processing['qwen_max_new_tokens'])
    os.environ['QWEN_MEMORY_MAX_ATTEMPTS']=str(processing['qwen_memory_max_attempts'])
    os.environ['PYTHONHASHSEED']='0'
    os.environ['TMPDIR']=str(ROOT/'tmp');Path(os.environ['TMPDIR']).mkdir(exist_ok=True)
    # Import credentials from the existing deployment into process memory only.
    private=Path('/opt/streammeco/run/StreamMeCo/configs/api_config.json')
    if private.exists():
        for item in read(private).values():
            if item.get('api_key_env') and item.get('api_key'):
                os.environ.setdefault(item['api_key_env'],item['api_key'])
    os.environ['PYTHONPATH']=os.pathsep.join([str(ROOT/'source/StreamMeCo'),str(ROOT/'source'),str(ROOT/'source/Mandol/src'),'/opt/streammeco/repos/3D-Speaker'])
    mandol_dir=ROOT/'mandol_runtime';mandol_dir.mkdir(exist_ok=True)
    if not (mandol_dir/'naver').exists():(mandol_dir/'naver').symlink_to('/opt/streammeco/run/Mandol/naver',target_is_directory=True)
    os.environ.pop('EGOLIFE_GEMINI_ONLY',None)
    os.environ.pop('EGOLIFE_RESULTS',None)  # ASR must fail closed.


def collect_evidence(snapshot, directory, session, plan):
    from mmagent.clip_audit import graph_view
    observations=[];segments=[];gaps=[];assignments=[]
    def sec(t):
        a,b=map(float,t.split(':'));return a*60+b
    for event in plan:
        if event['clip_id']>snapshot.cutoff_clip_id:break
        clip=event['clip_id']
        source=event.get('source')
        segments.append(dict(segment_id=clip,absolute_start_seconds=event['start_s'],
            absolute_end_seconds=event['end_s'],gap=event['gap'],
            source=source['path'] if source else None,
            start_seconds_in_source=event['start_s']-source['start_s']+source.get('source_offset_s',0) if source else 0))
        if event['gap']:
            gaps.append(dict(clip_id=clip,reason=event['gap'],start_s=event['start_s'],end_s=event['end_s']));continue
        audit=read(directory/'audits'/f'clip_{clip}_audit.json')
        for i,row in enumerate(audit['voice_observations']):
            start=round(event['start_s']+sec(row['start_time']),6);end=round(event['start_s']+sec(row['end_time']),6)
            if end>event['end_s']+1e-6 or end<=start:raise ValueError('ASR observation exceeds committed interval')
            uid=f'{session}/utt_{clip:06d}_{row["source_row_index"]:04d}'
            mapping=row.get('assignment_scores')
            if mapping is None:raise ValueError('voice audit lacks recorded pre-mutation scores')
            threshold=mapping['threshold']
            candidates=mapping.get('candidates')
            if candidates is None:
                candidates=[dict(candidate_id=k,score=v,eligible=v>=threshold,
                    rejection_reason=None if v>=threshold else 'below_threshold')
                    for k,v in mapping['candidate_scores'].items()]
            assignments.append(dict(evidence_id='assignment/'+uid,kind='historical_assignment',
                session_id=session,utterance_id=uid,available_at=end,
                method=mapping.get('method','TST'),candidates=candidates,threshold=threshold,
                selected_candidate=None if mapping['created_new_identity'] else 'voice_'+str(row['voice_node_id']),
                decision='new_voice' if mapping['created_new_identity'] else 'match',
                score_origin='historical_pre_mutation',model_version=mapping.get('method_id','CAM++'),
                source_audit=str(directory/'audits'/f'clip_{clip}_audit.json')))
            observations.append(dict(utterance_id=uid,session_id=session,clip_id=clip,
                start_time=start,end_time=end,original_voice_id='voice_'+str(row['voice_node_id']),
                transcripts={'Deepgram':row['asr']},original_transcript=row['asr'],
                audio_ref=str(directory/'intermediate'/f'clip_{clip}_voices.tst.json')+f"#/rows/{row['source_row_index']}/audio_segment",
                assignment_run_id=f'{session}/online/clip_{clip}',created_graph_version='online_'+str(clip),
                original_assignment_evidence=dict(kind='online_committed_voice_mapping',source_graph=str(directory/'checkpoint.pkl'))))
    memories=[]
    for node in snapshot.graph.nodes.values():
        if node.type not in ('episodic','semantic'):continue
        clip=node.metadata['timestamp'];end=snapshot.graph.segment_times[clip][1]
        if end>snapshot.cutoff_timestamp:raise ValueError('future memory')
        memories.append(dict(memory_node_id=str(node.id),kind=node.type,clip_id=clip,available_at=end,
            raw_text='\n'.join(node.metadata['contents']),raw_contents=list(node.metadata['contents']),
            epistemic_status='model-generated semantic claim' if node.type=='semantic' else 'model-generated event'))
    from bench_common import jsonl
    assignment_path=directory/'consolidation'/f'assignments_{snapshot.graph_version}.jsonl'
    jsonl(assignment_path,assignments)
    return dict(assignment_jsonl=assignment_path,replay=dict(session_id=session,source_graph_version='online_'+str(snapshot.graph_version),
        observations=observations,memories=memories,current_cutoff=snapshot.cutoff_timestamp,
        graph=graph_view(snapshot.graph),source_gaps=gaps,segments=segments,origin_seconds=0,source_root=str(directory)))


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
