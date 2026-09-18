"""Validate both real recall rounds, their lineage, evidence and exact review artifacts."""
import hashlib,json
from pathlib import Path
from .common import read,write
from .pipeline import load_current

def main():
    root=Path('consolidation/runs/recall_20')
    old=read(Path(read('consolidation/runs/live/checkpoint_20.json')['path'])/'state.json')
    source=read('egolife_m3_jake_day1/provenance/raw/gemini/results/clip_audits/clip_41_graph.json')
    checks=[]
    for n in (1,2):
        case=root/f'round_{n}';summary=read(case/'checkpoint_20.json');version=Path(summary['path'])
        state=load_current(case/'published',old['session_id'])
        graph,index,packet,report=[read(version/(x+'.json')) for x in ('graph','retrieval','evidence','execution')]
        assert packet['base_graph_version']==old['graph_version']
        assert packet['registry']==old['entities']
        assert graph['nodes']==source['nodes'] and graph['edges']==source['edges']
        assert graph['graph_version']==index['graph_version']==state['graph_version']
        assert index['model_id']=='text-embedding-3-large'
        assert all(len(v)==3072 for v in index['dense_vectors'])
        assert all(o['end_time']<=packet['current_cutoff'] for o in packet['observations'])
        assert packet['moss']==read('consolidation/runs/live/moss/prefix_20/moss.json')
        assert json.loads((version/'llm_output.txt').read_text())==read(version/'patch.json')
        review=case/'review/20min'
        for name,record in read(review/'metadata/manifest.json')['artifacts'].items():
            assert hashlib.sha256((review/name).read_bytes()).hexdigest()==record['sha256']
        assert (review/'04_astra_raw_output.txt').read_bytes()==(version/'llm_output.txt').read_bytes()
        assert (review/'metadata/astra_request.json').read_bytes()==(version/'llm_input.json').read_bytes()
        for item in state.get('assignment_history',[]):
            assert item['utterance_id'] in {o['utterance_id'] for o in packet['observations']}
            assert all(e in packet['evidence'] for e in item['evidence_ids'])
        checks.append(dict(round=n,assigned=len(state['assignments']),total=len(packet['observations']),
            accepted=len(report['accepted']),rejected=len(report['rejected']),version=state['graph_version']))
        old=state
    write(root/'verification.json',dict(status='passed',checks=checks,
        source_preserved=True,sequential_lineage=True,exact_artifacts=True,dense_dimensions=3072,
        identity_accuracy='not measured; independent gold unavailable'))
    print(json.dumps(checks,indent=2))

if __name__=='__main__':main()
