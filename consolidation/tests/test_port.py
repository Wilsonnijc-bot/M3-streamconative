import json
from types import SimpleNamespace

import pytest

from consolidation.port import consolidate, fetch_voice_log


def test_log_prefix_preserves_scores_and_rejects_conflicts(tmp_path):
    path = tmp_path / 'assignments.jsonl'
    event = dict(session_id='s', utterance_id='u', evidence_id='assignment/u',
                 available_at=5, candidates=[dict(score=0.123456789012345)], method='TST')
    future = dict(event, utterance_id='future', evidence_id='assignment/future', available_at=20)
    pending = dict(event, utterance_id='pending', evidence_id='assignment/pending')
    path.write_text('\n'.join(json.dumps(e) for e in (event, future, pending, event)) + '\n')
    replay = dict(session_id='s', current_cutoff=10, observations=[dict(utterance_id='u')])
    assert fetch_voice_log(path, replay) == [event]
    with path.open('a') as handle:
        handle.write(json.dumps(dict(event, method='CAM++')) + '\n')
    with pytest.raises(ValueError, match='conflicting'):
        fetch_voice_log(path, replay)


def test_foreign_log_fails(tmp_path):
    path = tmp_path / 'log'
    path.write_text(json.dumps(dict(session_id='other')) + '\n')
    with pytest.raises(ValueError, match='session'):
        fetch_voice_log(path, dict(session_id='s', observations=[]))


def test_port_delegates_publication_and_preserves_input(tmp_path, monkeypatch):
    from consolidation import native, pipeline
    from consolidation import prompt_packet
    path = tmp_path / 'log'
    path.write_text('')
    graph = SimpleNamespace(value=1)
    replay = dict(session_id='s', observations=[], current_cutoff=10)
    def prepare(inputs, output, moss, assignments, native_graph):
        assert assignments == [] and moss == {'window': 1}
        native_graph.value = 2
        inputs['native_graph'] = native_graph
        return {}, {'packet': True}
    def publish(inputs, output, state, packet, patch, **kwargs):
        assert inputs['native_graph'].value == 2 and patch == {'decision': True}
        return tmp_path / 'published', {'accepted': ['d'], 'rejected': []}
    monkeypatch.setattr(pipeline, 'prepare', prepare)
    monkeypatch.setattr(pipeline, 'publish', publish)
    monkeypatch.setattr(prompt_packet, 'prepare_prompt', lambda *args: None)
    monkeypatch.setattr(native, 'load_graph', lambda path: SimpleNamespace(value=3))
    result = consolidate(graph, replay, assignment_jsonl=path, work=tmp_path / 'work',
        output=tmp_path / 'out', moss={'window': 1}, proposer=lambda *args: {'decision': True})
    assert result.graph.value == 3 and graph.value == 1
    assert 'native_graph' not in replay
    assert (tmp_path / 'work/result.json').exists()


def test_port_requires_moss_before_model_call(tmp_path):
    with pytest.raises(ValueError, match='MOSS'):
        consolidate(SimpleNamespace(), {}, assignment_jsonl='missing', work=tmp_path,
                    output=tmp_path, proposer=lambda *args: pytest.fail('unexpected model call'))


def test_port_native_publication(tmp_path, monkeypatch):
    import pickle
    from consolidation.tests.test_native_characters import graph, publication_inputs
    from consolidation import reindex_cycle
    from consolidation.common import read, write
    g = graph()
    replay, _, _, patch = publication_inputs(g)
    replay['graph']['nodes'] = [dict(id=n.id, type=n.type) for n in g.nodes.values()]
    before = pickle.dumps(g)
    event = dict(session_id='s', utterance_id='u0', evidence_id='assignment/u0',
                 available_at=1, method='CAM++', candidates=[dict(score=0.81)])
    log = tmp_path / 'assignments.jsonl'
    log.write_text(json.dumps(event) + '\n')
    def build(staged, graph, config):
        write(staged / 'mandol/test_index.json', {'version': graph.graph_version})
        return dict(status='ready', graph_version=graph.graph_version)
    monkeypatch.setattr(reindex_cycle, 'build_retrieval_bundle', build)
    class Embed:
        def encode(self, texts):
            return [[0., 1., 0.] for _ in texts]
    result = consolidate(g, replay, assignment_jsonl=log, work=tmp_path / 'work',
        output=tmp_path / 'publications', proposer=lambda *args: patch,
        allow_no_moss=True, embedder=Embed())
    assert pickle.dumps(g) == before
    assert not result.report['rejected']
    assert 'character_1' in result.graph.retired_character_ids
    assert read(result.directory / 'evidence.json')['original_assignments'] == [event]
    assert (result.directory / 'mandol/test_index.json').exists()


def test_online_port_defers_until_public_barrier_and_reindexes(tmp_path):
    from consolidation.port import attach_online
    from consolidation.tests.test_native_characters import graph, publication_inputs
    g=graph();replay,_,_,patch=publication_inputs(g)
    replay['graph']['nodes']=[dict(id=n.id,type=n.type) for n in g.nodes.values()]
    calls=[]
    def propose(packet,work):
        calls.append(packet)
        return dict(patch,base_graph_version=packet['base_graph_version'])
    runtime=attach_online(g,lambda snapshot:dict(replay=replay),tmp_path,
        proposer=propose,moss=False,period_s=10,embed=lambda texts:[[0.,1.,0.] for _ in texts])
    try:
        with runtime.segment(1,10):pass
        assert not calls
        report=runtime.consolidate_until(10)
        assert len(calls)==1 and report['accepted_decisions']==1
        assert report['reindex_ms']>=0 and report['write_back_ms']>=0
        assert g.last_consolidated_timestamp==10 and not g.identity_dirty
        assert 'character_1' in g.retired_character_ids
        with pytest.raises(ValueError,match='already consolidated'):
            runtime.consolidate_until(10)
    finally:runtime.close(flush_final=False)
