"""Inspect real smoke artifacts and publish a content-bound full-launch gate."""
import argparse
from pathlib import Path
import pickle
from bench_common import ROOT,atomic,read,rows,sha
from online_benchmark import source_fingerprint
from runtime_support import environment


def audit_prefix(prefix,dataset):
    folder=prefix/dataset;receipt=folder/'SMOKE_PASS.json';assert read(receipt)['status']=='passed'
    evidence=[receipt,folder/'CURRENT.json',folder/'events.jsonl']
    ev=rows(folder/'events.jsonl');assert ev and all(e['temporary_removed'] for e in ev)
    assert any(e['temporary_peak_bytes']>0 for e in ev)
    results=list(folder.glob('C*/snapshots/*/answers/*/R*/result.json'));assert len(results)==8
    seen={};summary={}
    for path in results:
        r=read(path);method=r['construction_method'];retrieval=r['retrieval_method']
        assert r['answer_calls']==r['retrieval_calls']==r['answer']['answer_calls']==r['retrieval']['retrieval_calls']==1
        assert r['answer']['model']=='gpt-5.6-terra' and r['answer']['ttft_ms']>0
        snapshot=ROOT/r['snapshot'];assert sha(snapshot)==r['snapshot_sha256']==r['retrieval']['snapshot_sha256']
        seen.setdefault(method,set()).add(r['snapshot_sha256'])
        g=pickle.loads(snapshot.read_bytes())
        for voice in (n for n in g.nodes.values() if n.type=='voice'):
            if method!='C1':
                assert voice.metadata['embedding_space']=='speechbrain_ecapa_192' and voice.embeddings
                assert voice.metadata['method_id']==read(ROOT/'configs'/f'tst_{dataset}.json')['method_id']
            else:assert voice.metadata.get('embedding_space')!='speechbrain_ecapa_192'
        for n in g.nodes.values():
            if n.type in ('episodic','semantic'):assert g.segment_times[n.metadata['timestamp']][1]<=r['benchmark_timestamp']
        events=read(path.parent/'stream_events.json')
        first=next(e for e in events if e['type']=='response.output_text.delta' and e['delta'])
        assert first['wall_ts']==r['answer']['first_content_token_ts']
        assert read(path.parent/'response.json')['status']=='completed'
        if retrieval=='R2':
            reranking=r['retrieval']['metrics']['reranking']
            assert reranking['calls']==1 and reranking['status']=='success'
            assert reranking['endpoint']=='https://api.302.ai/v1/rerank'
            assert {c['method'] for c in r['retrieval']['metrics']['components']}=={'BM25','COSINE_SIMILARITY','SPLADE'}
        summary[method+'_'+retrieval]=dict(ttft_ms=r['answer']['ttft_ms'],response_ms=r['answer']['generation_complete_ms'],hash=r['snapshot_sha256'])
        evidence.extend([path,snapshot,path.parent/'stream_events.json',path.parent/'response.json',path.parent/'request.json'])
    assert set(seen)=={'C1','C2','C3','C4'} and all(len(v)==1 for v in seen.values())
    for method in seen:
        audits=rows(folder/method/'construction.jsonl');assert audits
        for audit in audits:
            if audit.get('gap'):continue
            voice=audit['stage_details']['voice']
            assert voice['speaker_mapping']==('CAM++' if method=='C1' else 'TST')
            if method!='C1':
                for mapping in voice.get('tst_mappings',[]):assert mapping['enrollment_policy']=='online_native_m3'
        evidence.append(folder/method/'construction.jsonl')
        builds=list((folder/method).glob('snapshots/*/mandol_build.json'));assert len(builds)==1
        initialization=builds[0].parent/'mandol_initialization.json'
        assert read(initialization)['excluded_from_warm_retrieval'] is True
        evidence.append(initialization)
        assert read(builds[0])['manifest']['counts']['relation_llm_calls']==0
        evidence.extend(builds)
    return summary,evidence


def main():
    p=argparse.ArgumentParser();p.add_argument('--jake',type=Path,required=True);p.add_argument('--aea',type=Path,required=True);p.add_argument('--maintenance',type=Path,required=True);a=p.parse_args()
    environment();evidence=[];summary={}
    for dataset,prefix in [('jake',a.jake.resolve()),('aea',a.aea.resolve())]:
        summary[dataset],paths=audit_prefix(prefix,dataset);evidence+=paths
    maintenance=a.maintenance.resolve();assert read(maintenance/'PASS.json')['status']=='passed';evidence.append(maintenance/'PASS.json')
    for method in ('C3','C4'):
        events=rows(maintenance/method/'consolidation.jsonl')
        assert [e['media_timestamp'] for e in events]==[1200,2400,3600]
        assert all(e['status']=='accepted' and e['llm_call_count']==1 for e in events)
        for event in events:
            job=ROOT/event['job_directory']
            assert read(job/'llm_metadata.json')['returned_model']=='gpt-5.6-sol'
            for name in ['snapshot.pkl','evidence.json','patch.json','execution.json','identity_changes.json','phase_timings.json','llm_response.json']:
                assert (job/name).is_file();evidence.append(job/name)
            packet=read(job/'evidence.json')
            moss=packet['moss']
            assert moss['cutoff_s']==event['media_timestamp']
            assert moss['start_s']==packet['previous_cutoff']
            assert all(o['assignment_run_id'] for o in packet['observations'])
            assert packet['original_assignments'], 'recorded voice similarity evidence missing'
            request=read(job/'llm_input.json')
            assert request['model']=='gpt-5.6-sol' and request['reasoning']['effort']=='high'
            evidence.append(job/'llm_input.json')
            for path in (job/'moss').rglob('*.json'):evidence.append(path)
        hour=maintenance/method/'hour_01'
        for name in ('graph.pkl','memory.md','latency.md','retrieval.md'):assert (hour/name).stat().st_size>0;evidence.append(hour/name)
        g=pickle.loads((hour/'graph.pkl').read_bytes());assert g.last_consolidated_timestamp==3600 and not g.identity_dirty
        assert read(hour/'state.json')['compression']['requested_ratio']==(.5 if method=='C3' else .7)
        evidence.append(maintenance/method/'consolidation.jsonl')
    static=read(ROOT/'metadata/prefix_static.json');assert static['passed'] and static['skipped']==0 and static['tests']>=15
    evidence.append(ROOT/'metadata/prefix_static.json')
    assert read(ROOT/'metadata/readiness.json')['status']=='ready'
    assert not any(p.suffix.lower() in ('.mp4','.wav','.avi','.mkv') for p in (ROOT/'tmp').rglob('*') if p.is_file()),'temporary media not fully removed'
    gate=dict(status='passed',prefix_summary=summary,static_tests=static,
        maintenance_scope='real GPU prefix plus synthetic missing-media intervals, not an hour of observed media',
        validated_source_sha256=source_fingerprint(),evidence_sha256={str(p.relative_to(ROOT)):sha(p) for p in evidence})
    atomic(ROOT/'metadata/validation_gate.json',gate);print('VALIDATION_GATE_READY',len(evidence),flush=True)

if __name__=='__main__':main()
