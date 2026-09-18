from pathlib import Path
import pytest
from consolidation.replay import load_replay
from consolidation.pipeline import prepare,publish,load_current
from consolidation.common import read

ROOT=Path(__file__).resolve().parents[2]


@pytest.fixture(scope='module')
def replays():
    return [load_replay(ROOT/'egolife_m3_jake_day1','ego',cutoff) for cutoff in (1200,2400)]


def test_real_cutoffs_no_future_and_source_preservation(replays):
    first,second=replays
    assert first['current_cutoff']==1187.92
    assert second['current_cutoff']==2387.92
    assert [len(r['observations']) for r in replays]==[224,421]
    assert not first['source_gaps'] and not second['source_gaps']
    assert first['observations']==second['observations'][:len(first['observations'])]
    assert '740' not in {m['memory_node_id'] for m in first['memories']}
    assert '740' in {m['memory_node_id'] for m in second['memories']}
    for replay in replays:
        assert all(o['end_time']<=replay['current_cutoff'] for o in replay['observations'])
        assert all(m['available_at']<=replay['current_cutoff'] for m in replay['memories'])
        assert sum(o['original_voice_id'] is None for o in replay['observations'])==2
        assert all(o['original_assignment_evidence']['scores_status']=='not_recorded' for o in replay['observations'])


def test_incremental_registry_and_historical_views(replays,tmp_path):
    first,second=replays
    state,packet=prepare(first,tmp_path)
    p=dict(schema_version=1,session_id='ego',base_graph_version=state['graph_version'],evidence_cutoff_s=1187.92,
           decisions=[dict(decision_id='d',op='merge_voice',voice_ids=['voice_364'],target_entity_id='person_0',evidence_ids=['semantic_372'])])
    path,_=publish(first,tmp_path,state,packet,p)
    before=load_current(tmp_path,'ego')
    state,packet=prepare(second,tmp_path)
    assert state==before and packet['previous_cutoff']==1187.92
    p.update(base_graph_version=state['graph_version'],evidence_cutoff_s=2387.92,decisions=[])
    newpath,_=publish(second,tmp_path,state,packet,p)
    after=load_current(tmp_path,'ego')
    assert before['assignments']==after['assignments']
    assert path!=newpath
    assert read(path/'state.json')==before
    assert read(newpath/'graph.json')['nodes']==second['graph']['nodes']


def test_exact_review_bundle_preserves_model_artifacts(tmp_path):
    import json
    from consolidation.common import write
    from consolidation.review_bundle import build_review
    for minutes,clip,cutoff in [(20,41,1187.92),(40,83,2387.92)]:
        write(tmp_path/f'metadata/prefix_{minutes}.json',{'current_cutoff':cutoff,'segments':[{'segment_id':clip}]})
    moss=tmp_path/'moss/prefix_20'
    write(moss/'raw_output.json',{'text':'[0][S01]原文、不改写。[1]'})
    work=tmp_path/'metadata/astra_20'
    payload={'instructions':'Exact instructions\nsecond line','input':[{'role':'user','content':'{"evidence": "原文"}'}]}
    write(work/'llm_input.json',payload)
    raw='{"decisions": []}\n'
    (work/'llm_output.txt').write_text(raw,encoding='utf-8')
    write(work/'llm_response.json',{'id':'test','output':raw})
    output=build_review(tmp_path)
    assert (output/'20min/02_moss_transcript.txt').read_text()=='[0][S01]原文、不改写。[1]'
    assert (output/'20min/04_astra_raw_output.txt').read_bytes()==(work/'llm_output.txt').read_bytes()
    assert (output/'20min/metadata/astra_request.json').read_bytes()==(work/'llm_input.json').read_bytes()
    prompt=(output/'20min/03_astra_prompt.md').read_text()
    assert payload['instructions'] in prompt and payload['input'][0]['content'] in prompt
    assert not (output/'40min/04_astra_raw_output.txt').exists()
    assert 'pending' in (output/'README.md').read_text()
