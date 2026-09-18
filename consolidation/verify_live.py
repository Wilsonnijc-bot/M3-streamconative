"""Verify published live versions and the exact review copies; no identity gold inferred."""
import hashlib
import json
from pathlib import Path
from .common import read,write
from .pipeline import load_current


def main():
    root=Path('consolidation/runs/live')
    checks=[]
    for minutes,clip in [(20,41),(40,83)]:
        summary=read(root/f'checkpoint_{minutes}.json')
        version=Path(summary['path'])
        manifest=read(version/'manifest.json')
        for name,sha in manifest['sha256'].items():
            assert hashlib.sha256((version/name).read_bytes()).hexdigest()==sha
        graph,state,index,packet=[read(version/(name+'.json')) for name in ['graph','state','retrieval','evidence']]
        source=read(f'egolife_m3_jake_day1/provenance/raw/gemini/results/clip_audits/clip_{clip}_graph.json')
        assert graph['nodes']==source['nodes'] and graph['edges']==source['edges']
        assert graph['graph_version']==state['graph_version']==index['graph_version']
        assert index['model_id']=='text-embedding-3-large'
        assert all(len(v)==3072 for v in index['dense_vectors'])
        assert all(o['end_time']<=packet['current_cutoff'] for o in packet['observations'])
        assert all(m['available_at']<=packet['current_cutoff'] for m in packet['memories'])
        assert set(state['assignments'].values())<=set(state['entities'])
        assert json.loads((version/'llm_output.txt').read_text())==read(version/'patch.json')
        review=root/f'review/{minutes}min'
        for name,record in read(review/'metadata/manifest.json')['artifacts'].items():
            assert hashlib.sha256((review/name).read_bytes()).hexdigest()==record['sha256']
        assert (review/'04_astra_raw_output.txt').read_bytes()==(version/'llm_output.txt').read_bytes()
        assert (review/'metadata/astra_request.json').read_bytes()==(version/'llm_input.json').read_bytes()
        checks.append({'minutes':minutes,'version':state['graph_version'],'source_graph_preserved':True,
                       'future_evidence_absent':True,'dense_dimensions':3072,'exact_review_verified':True})
    first=read(Path(read(root/'checkpoint_20.json')['path'])/'state.json')
    second_packet=read(Path(read(root/'checkpoint_40.json')['path'])/'evidence.json')
    assert second_packet['base_graph_version']==first['graph_version']
    assert second_packet['previous_cutoff']==first['cutoff']
    assert second_packet['registry']==first['entities']
    load_current(root/'published','egolife_m3_jake_day1/gemini')
    write(root/'verification.json',{'status':'passed','checks':checks,'sequential_registry_verified':True,
                                  'identity_accuracy':'not measured; no independent gold labels'})
    print('LIVE_VERSION_VERIFICATION_PASSED',flush=True)


if __name__=='__main__':main()
