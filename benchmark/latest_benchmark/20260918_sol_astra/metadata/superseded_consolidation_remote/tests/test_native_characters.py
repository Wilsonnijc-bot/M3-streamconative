import copy
import pickle
from pathlib import Path

import pytest

from consolidation.native import m3_module, proposal_state, publish_native, current_graph
from consolidation.common import read

identity = m3_module('mmagent.character_identity')
VideoGraph = m3_module('mmagent.videograph').VideoGraph


@pytest.fixture(autouse=True)
def deterministic_retrieval_builder(monkeypatch):
    from consolidation import reindex_cycle
    from consolidation.common import write
    def build(staged, graph, config):
        write(Path(staged)/'mandol/test_index.json', {'version':graph.graph_version})
        return dict(status='ready', graph_version=graph.graph_version)
    monkeypatch.setattr(reindex_cycle, 'build_retrieval_bundle', build)


def graph():
    g = VideoGraph()
    g.add_voice_node({'contents': ['a', 'b'], 'embeddings': [[1., 0., 0.]]})
    g.add_voice_node({'contents': ['c'], 'embeddings': [[0., 1., 0.]]})
    g.add_img_node({'contents': ['face'], 'embeddings': [[0., 0., 1.]]})
    for text in ('<voice_0> speaks', '<voice_1> listens', '<face_2> smiles', 'The room is quiet'):
        g.add_text_node({'contents': [text], 'embeddings': [[1., 0., 0.]]}, 1)
    g.order_character()
    return g


def obs(uid, feature, entity):
    return dict(observation_id=uid, feature_id=feature, entity_id=entity,
                confidence=.85, evidence_ids=['e1'])


def apply(g, mixed=False, refs=(), **kwargs):
    return identity.apply_conclusions(g,
        {'a': {'canonical_name': 'Alice'}, 'b': {'canonical_name': None}},
        [obs('u0', 'voice_0', 'a'), obs('u1', 'voice_0', 'b' if mixed else 'a'),
         obs('u2', 'voice_1', 'a'), obs('f0', 'face_2', 'b')], list(refs),
        cutoff=10, provenance={'reviewed_memory_ids': [3, 4, 5, 6]}, **kwargs)


def test_stable_merge_names_and_native_only_reload():
    g = graph(); result = apply(g)
    assert result['conclusion_characters'] == {'a': 'character_0', 'b': 'character_2'}
    assert result['retired_characters'] == {'character_1': 'character_0'}
    assert g.character_mappings['character_0'] == ['voice_0', 'voice_1']
    assert g.resolve_identity('voice_1')['identity'] == 'Alice'
    assert g.resolve_identity('face_2')['identity'] == 'character_2'
    g.identity_history = []  # Runtime resolution does not need proposal aliases/provenance.
    restored = pickle.loads(pickle.dumps(g))
    assert restored.resolve_identity('voice_1')['character_id'] == 'character_0'
    assert restored.resolve_identity('voice_999')['identity'] == 'voice_999'


def test_mixed_scopes_and_occurrence_precedence():
    g = graph()
    g.nodes[3].metadata['contents'] = ['<voice_0> meets <voice_0>']
    refs = [dict(memory_node_id='3', mention='<voice_0>', entity_id='a', content_index=0, start=0, end=9),
            dict(memory_node_id='3', mention='<voice_0>', entity_id='b', content_index=0, start=16, end=25)]
    # Actual second token starts at 16.
    apply(g, mixed=True, refs=refs)
    assert 'voice_0' not in g.reverse_character_mappings
    assert g.resolve_identity('voice_0')['identity'] == 'voice_0'
    assert g.resolve_identity('voice_0', observation_id='u0')['identity'] == 'Alice'
    assert g.resolve_identity('voice_0', observation_id='u1')['identity'].startswith('character_')
    key = identity.reference_key(3, 0, 16, 25)
    assert g.resolve_identity('voice_0', observation_id='u0', memory_reference=key)['identity'] == 'Alice'
    texts, traces = identity.canonicalize_contents(g, g.nodes[3].metadata['contents'], node_id=3)
    assert texts == ['Alice meets ' + g.observation_character_mappings['u1']]
    assert all(t['source'] == 'memory_reference_override' for t in traces)


def test_repeated_correction_refresh_and_partial_move():
    g = graph(); apply(g, mixed=True)
    ids = set(g.character_mappings)
    original = copy.deepcopy(g.character_metadata)
    g.refresh_equivalences(); g.order_character()
    assert g.character_metadata == original and set(g.character_mappings) == ids
    assert 'voice_0' not in g.reverse_character_mappings
    a = g.observation_character_mappings['u0']; b = g.observation_character_mappings['u1']
    identity.apply_conclusions(g,
        {'a': {'canonical_name': 'Alicia', 'native_character_id': a},
         'b': {'canonical_name': None, 'native_character_id': b}},
        [obs('u0', 'voice_0', 'a'), obs('u1', 'voice_0', None), obs('u2', 'voice_1', 'a'), obs('f0', 'face_2', 'b')],
        [], cutoff=20, provenance={'reviewed_memory_ids': [3]})
    assert 'u1' not in g.observation_character_mappings
    assert g.resolve_identity('voice_1')['identity'] == 'Alicia'
    assert set(g.character_mappings) == ids
    assert b not in g.retired_character_ids


def test_majority_strict_threshold_and_no_provisional_votes():
    g = graph(); apply(g, mixed=True)
    a = g.observation_character_mappings['u0']
    g.reviewed_feature_support['voice_0'] = dict(counts={a: 8}, total=9, complete=False)
    identity.admit_observations(g, 'voice_0', ['new'], 2)
    assert g.observation_character_mappings['voice_0/content_2'] == a  # 8/10
    identity.admit_observations(g, 'voice_0', ['more'], 3)
    assert 'voice_0/content_3' not in g.observation_character_mappings  # 8/11
    assert g.reviewed_feature_support['voice_0']['counts'] == {a: 8}
    assert g.resolve_identity('voice_0')['source'] == 'raw_fallback'
    g.reviewed_feature_support['voice_0'] = dict(counts={a: 3}, total=3)
    identity.admit_observations(g, 'voice_0', ['exactly'], 4)
    assert 'voice_0/content_4' not in g.observation_character_mappings  # 3/4


def test_selective_reindex_atomic_failure_and_query_path():
    g = graph(); original = pickle.dumps(g); apply(g)
    before = {n: copy.deepcopy(node.embeddings) for n, node in g.nodes.items()}
    calls = []
    def embed(texts):
        calls.append(texts)
        return [[0., 1., 0.] for _ in texts]
    report = g.reindex_identity_text(embed)
    assert report['changed_node_ids'] == [3, 4, 5]
    assert calls == [['Alice speaks', 'Alice listens', 'character_2 smiles']]
    assert g.nodes[6].embeddings == before[6]
    assert all(g.nodes[i].embeddings == before[i] for i in (0, 1, 2))
    assert g.nodes[3].metadata['contents'] == ['<voice_0> speaks']
    assert not g.reindex_identity_text(embed)['changed_node_ids']
    retrieve = m3_module('mmagent.retrieve')
    assert retrieve.back_translate(g, ['What did Alice do?']) == ['What did Alice do?']
    assert retrieve.translate(g, g.nodes[3].metadata['contents'], node_id=3) == ['Alice speaks']
    g.character_metadata['character_0']['canonical_name'] = 'Alicia'
    checkpoint = pickle.dumps(g)
    with pytest.raises(ValueError):
        g.reindex_identity_text(lambda texts: [])
    assert pickle.dumps(g) == checkpoint
    legacy = pickle.loads(original)
    assert retrieve.translate(legacy, ['<voice_0> speaks']) == ['<character_0> speaks']
    assert retrieve.back_translate(legacy, ['<character_0> speaks']) == ['<voice_0> speaks']


def test_unreviewed_incomplete_feature_and_face_mixed():
    g = graph()
    identity.apply_conclusions(g, {'a': {'canonical_name': 'Alice'}},
        [obs('u0', 'voice_0', 'a')], [], cutoff=10, provenance={})
    assert g.resolve_identity('voice_0')['source'] == 'raw_fallback'
    g.nodes[2].metadata['contents'].append('second face')
    identity.apply_conclusions(g, {'a': {'canonical_name': 'Alice'}, 'b': {'canonical_name': None}},
        [obs('f0', 'face_2', 'a'), obs('f1', 'face_2', 'b')], [], cutoff=20, provenance={})
    assert g.resolve_identity('face_2')['source'] == 'raw_fallback'
    assert g.resolve_identity('face_2', observation_id='f0')['identity'] == 'Alice'
    assert g.resolve_identity('face_2', observation_id='f1')['identity'].startswith('character_')


def test_construction_preembedding_and_precomputed_validation(monkeypatch):
    g = graph(); apply(g); g.reindex_identity_text(lambda xs: [[1., 0., 0.] for _ in xs])
    processing = m3_module('mmagent.memory_processing_qwen')
    seen = []
    monkeypatch.setattr(processing, 'get_embeddings_batch', lambda model, texts: (seen.append(texts) or [[1., 0., 0.] for _ in texts], 0))
    processing.process_memories(g, ['<voice_1> walks'], 2)
    assert seen == [['Alice walks']]
    node = g.nodes[g.next_node_id - 1]
    assert node.metadata['contents'] == ['<voice_1> walks']
    assert node.metadata['retrieval_contents'] == ['Alice walks']
    with pytest.raises(ValueError, match='precomputed'):
        processing.process_memories(g, ['<voice_1> walks'], 2, precomputed_embeddings=[[1., 0., 0.]],
                                    precomputed_contents=['<voice_1> walks'])


def test_native_mandol_export_mixed_feature(tmp_path):
    g = graph(); apply(g, mixed=True)
    g.reindex_identity_text(lambda xs: [[1., 0., 0.] for _ in xs])
    path = tmp_path / 'graph.pkl'; path.write_bytes(pickle.dumps(g))
    export = m3_module('m3_agent.export_mandol')
    export.export_graph(path, tmp_path / 'export', 'test')
    import json
    records = [json.loads(line) for line in (tmp_path / 'export/memories.jsonl').read_text().splitlines()]
    mixed = next(r for r in records if r['m3_node_id'] == '3')
    assert mixed['text'] == 'voice_0 speaks' and not mixed['canonical_entity_ids']
    assert all('person_' not in str(r) for r in records)


def publication_inputs(g):
    from consolidation.evidence_builder import build_evidence
    observations = [dict(utterance_id='u'+str(i), original_voice_id=voice,
        session_id='s', start_time=i, end_time=i+1, clip_id=1)
        for i, voice in enumerate(['voice_0','voice_0','voice_1'])]
    memories = [dict(memory_node_id=str(n.id), raw_text='\n'.join(n.metadata['contents']),
                    kind=n.type, available_at=10, clip_id=1)
                for n in g.nodes.values() if n.type in ('episodic','semantic')]
    replay = dict(session_id='s', source_graph_version='source', current_cutoff=10,
                  observations=observations, memories=memories, source_gaps=[], graph={'nodes':[]})
    state = proposal_state(g, 's', observations, 'source')
    packet = build_evidence(replay, state)
    patch = dict(schema_version=1, session_id='s', base_graph_version=state['graph_version'],
        evidence_cutoff_s=10, decisions=[dict(decision_id='merge',op='assign_cluster',
            voice_ids=['voice_0','voice_1'],target_entity_id='person_0',evidence_ids=['u0'],
            confidence=.9,rationale='Continuous speaker across fragmented features.',excluded_utterance_ids=[])])
    return replay,state,packet,patch


def test_native_transaction_repeated_merge_and_debug_independence(tmp_path):
    g = graph(); replay,state,packet,patch = publication_inputs(g)
    source = pickle.dumps(g)
    class Embed:
        def encode(self, texts):
            return [[0.,1.,0.] for _ in texts]
    path,_ = publish_native(replay,tmp_path,state,packet,patch,g,Embed())
    assert pickle.dumps(g) == source
    current = current_graph(tmp_path, 's')
    session = path.parent.parent
    assert VideoGraph.load_current(session).graph_version == current.graph_version
    assert 'character_1' in current.retired_character_ids
    first_ids = set(current.character_mappings)
    native_state = proposal_state(current, 's', replay['observations'], 'source')
    assert 'person_1' not in native_state['entities']
    from consolidation.evidence_builder import build_evidence
    packet2 = build_evidence(replay,native_state)
    patch2 = dict(patch,base_graph_version=current.graph_version,decisions=[])
    path2,_ = publish_native(replay,tmp_path,native_state,packet2,patch2,current,Embed())
    second = current_graph(tmp_path,'s')
    assert VideoGraph.load_current(session).graph_version == second.graph_version
    assert set(second.character_mappings)==first_ids
    assert not read(path2/'embedding_manifest.json')['changed_node_ids']
    assert path != path2
    # Retrieval and proposal preparation read the graph alone, not audit JSON.
    second.identity_history=[]
    native_state2 = proposal_state(second,'s',replay['observations'],'source')
    assert native_state2['assignments']==native_state['assignments']
    with pytest.raises(ValueError,match='base'):
        publish_native(replay,tmp_path,state,packet,patch,g,Embed())


def test_publication_failure_does_not_advance_or_mutate(tmp_path):
    g = graph(); replay,state,packet,patch = publication_inputs(g)
    before = pickle.dumps(g)
    class Broken:
        def encode(self, texts):
            raise RuntimeError('embedding failed')
    with pytest.raises(RuntimeError,match='embedding failed'):
        publish_native(replay,tmp_path,state,packet,patch,g,Broken())
    assert current_graph(tmp_path,'s') is None and pickle.dumps(g)==before


def test_invalid_reference_rolls_back_publication_and_new_feature_admission(tmp_path):
    g = graph(); apply(g)
    g.reindex_identity_text(lambda xs: [[1.,0.,0.] for _ in xs])
    with pytest.raises(ValueError,match='earlier'):
        g.identity_cutoff_clip=10
        g.truncate_memory_by_clip(5)
    character=g.resolve_identity('voice_0')['character_id']
    g.update_node(0,{'contents':['new'], 'embeddings':[[1.,0.,0.]]})
    assert 'voice_0' not in g.reverse_character_mappings
    assert g.identity_dirty
    assert g.observation_character_mappings['u0']==character
    # Its independently reviewed support is only 2/3, so the new turn is unvalidated.
    assert 'voice_0/content_2' not in g.observation_character_mappings


def test_runtime_has_no_consolidation_dependency():
    import subprocess, sys
    result=subprocess.run([sys.executable,'-c',
        "import sys; from mmagent.videograph import VideoGraph; "
        "g=VideoGraph(); assert not any(k=='consolidation' or k.startswith('consolidation.') for k in sys.modules); "
        "assert 'torch' not in sys.modules; print('native runtime independent')"],
        cwd=Path(__file__).resolve().parents[2]/'StreamMeCo', capture_output=True, text=True)
    assert result.returncode==0, result.stderr


def test_existing_retrieval_searches_native_vectors_without_query_rewriting(monkeypatch, tmp_path):
    g=graph(); apply(g, mixed=True)
    g.reindex_identity_text(lambda xs: [[0.,1.,0.] for _ in xs])
    retrieve=m3_module('mmagent.retrieve')
    queries=[]
    monkeypatch.setattr(retrieve,'parallel_get_embedding',
                        lambda model,texts: (queries.extend(texts) or [[0.,1.,0.]],0))
    monkeypatch.setattr(retrieve,'TIME_LOG_PATH',str(tmp_path/'timing.log'))
    clips,scores,nodes=retrieve.retrieve_from_videograph(g,'What did Alice do?')
    assert queries==['What did Alice do?']
    assert clips and nodes and all(node_id in g.text_nodes for node_id,_ in nodes)
    g.identity_cutoff_clip=10
    with pytest.raises(ValueError,match='earlier'):
        retrieve.retrieve_from_videograph(g,'What did Alice do?',before_clip=5)


def test_legacy_construction_entry_uses_native_text_and_configured_alias(monkeypatch):
    g=graph(); apply(g); g.reindex_identity_text(lambda xs: [[1.,0.,0.] for _ in xs])
    processing=m3_module('mmagent.memory_processing')
    calls=[]
    monkeypatch.setattr(processing,'parallel_get_embedding',
        lambda model,texts: (calls.append((model,texts)) or [[1.,0.,0.] for _ in texts],0))
    processing.process_memories(g,['<voice_1> walks'],2)
    assert calls==[('text-embedding-3-large',['Alice walks'])]


def test_reference_removal_and_new_character_monotonicity():
    g=graph()
    apply(g,refs=[dict(memory_node_id='3',mention='<voice_0>',entity_id='a')])
    assert g.reference_character_mappings
    ids=set(g.character_mappings)
    maximum=g.next_character_id
    identity.apply_conclusions(g,{'a':{'canonical_name':'Alice','native_character_id':'character_0'}},
        [obs('u0','voice_0','a'),obs('u1','voice_0','a'),obs('u2','voice_1','a')],[],
        cutoff=20,provenance={'reviewed_memory_ids':[3]})
    assert not g.reference_character_mappings
    new_id=identity.new_character(g)
    assert int(new_id.split('_')[-1])>=maximum
    assert new_id not in ids and new_id not in g.retired_character_ids


def test_unrelated_characters_and_partial_legacy_character_are_preserved():
    g=graph()
    # A legacy character contains both a reviewed voice and an unreviewed face.
    g.character_mappings={'character_4':['voice_0','face_2'],'character_17':['voice_1'],
                          'character_31':[]}
    identity.rebuild_reverse(g)
    report=identity.apply_conclusions(g,{'a':{'canonical_name':'Alice'},'b':{'canonical_name':'Bob'}},
        [obs('u0','voice_0','b'),obs('u1','voice_0','b'),obs('u2','voice_1','a')],[],
        cutoff=10,provenance={})
    assert g.character_mappings['character_31']==[]
    assert g.resolve_identity('face_2')['character_id']=='character_4'
    assert not report['retired_characters']


def test_later_prefix_keeps_new_native_nodes_and_previous_character_ids(tmp_path):
    g=graph(); replay,state,packet,patch=publication_inputs(g)
    class Embed:
        def encode(self,texts): return [[1.,0.,0.] for _ in texts]
    publish_native(replay,tmp_path,state,packet,patch,g,Embed())
    continued=current_graph(tmp_path,'s')
    new_id=continued.add_voice_node({'contents':['new turn'],'embeddings':[[1.,0.,0.]]})
    replay2=copy.deepcopy(replay)
    replay2['current_cutoff']=20
    replay2['observations'].append(dict(utterance_id='u3',original_voice_id='voice_'+str(new_id),
        session_id='s',start_time=11,end_time=12,clip_id=2))
    from consolidation.pipeline import prepare,publish
    state2,packet2=prepare(replay2,tmp_path,native_graph=continued)
    patch2=dict(patch,base_graph_version=continued.graph_version,evidence_cutoff_s=20,
        decisions=[dict(decision_id='extend',op='assign_cluster',voice_ids=['voice_'+str(new_id)],
            target_entity_id='person_0',evidence_ids=['u3'],confidence=.8,rationale='Same speaker continuation.',
            excluded_utterance_ids=[])])
    publish(replay2,tmp_path,state2,packet2,patch2,Embed())
    final=current_graph(tmp_path,'s')
    assert new_id in final.nodes
    assert final.resolve_identity('voice_'+str(new_id))['character_id']=='character_0'


def test_mandol_failure_keeps_previous_complete_version(tmp_path, monkeypatch):
    from consolidation import reindex_cycle
    from consolidation.pipeline import session_directory
    from consolidation.evidence_builder import build_evidence
    g=graph(); replay,state,packet,patch=publication_inputs(g)
    class Embed:
        def encode(self,texts): return [[1.,0.,0.] for _ in texts]
    first,_=publish_native(replay,tmp_path,state,packet,patch,g,Embed())
    head=read(session_directory(tmp_path,'s')/'CURRENT.json')
    current=current_graph(tmp_path,'s')
    state2=proposal_state(current,'s',replay['observations'],'source')
    packet2=build_evidence(replay,state2)
    patch2=dict(patch,base_graph_version=current.graph_version,decisions=[])
    def fail(*args): raise RuntimeError('Mandol unavailable')
    monkeypatch.setattr(reindex_cycle,'build_retrieval_bundle',fail)
    with pytest.raises(RuntimeError,match='Mandol unavailable'):
        publish_native(replay,tmp_path,state2,packet2,patch2,current,Embed())
    assert read(session_directory(tmp_path,'s')/'CURRENT.json')==head
    assert read(first/'retrieval_ready.json')['status']=='ready'
    assert current_graph(tmp_path,'s').graph_version==current.graph_version


def test_incorrect_mandol_version_cannot_publish(tmp_path, monkeypatch):
    from consolidation import reindex_cycle
    g=graph(); replay,state,packet,patch=publication_inputs(g)
    class Embed:
        def encode(self,texts): return [[1.,0.,0.] for _ in texts]
    monkeypatch.setattr(reindex_cycle,'build_retrieval_bundle',
                        lambda *args: {'status':'ready','graph_version':'wrong'})
    with pytest.raises(ValueError,match='not ready'):
        publish_native(replay,tmp_path,state,packet,patch,g,Embed())
    assert current_graph(tmp_path,'s') is None


def test_current_verifies_nested_retrieval_files(tmp_path):
    g=graph(); replay,state,packet,patch=publication_inputs(g)
    class Embed:
        def encode(self,texts): return [[1.,0.,0.] for _ in texts]
    version,_=publish_native(replay,tmp_path,state,packet,patch,g,Embed())
    (version/'mandol/test_index.json').write_text('{}')
    with pytest.raises(ValueError,match='integrity'):
        current_graph(tmp_path,'s')
