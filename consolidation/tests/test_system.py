import copy
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from consolidation.common import read,write
from consolidation.entity_registry import initial_state
from consolidation.evidence_builder import build_evidence
from consolidation.patch_executor import execute
from consolidation.observations import ObservationLedger
from consolidation.pipeline import publish,load_current,prepare,session_directory
from consolidation.canonicalizer import canonicalize
from consolidation.moss_alignment import align
from consolidation.moss_runner import parse_output
from consolidation.assignment_logger import AssignmentLogger,LoggedVoiceGraph
from consolidation.retrieval_refresh import HashEmbedder,search
from consolidation.evaluation import evaluate
from consolidation.replay import schedule


def fixture():
    obs=[dict(utterance_id='s/u'+str(i),session_id='s',clip_id=1,start_time=i*2,end_time=i*2+1,
        original_voice_id=v,transcripts={'MAI':'hello'},original_transcript='MAI: hello',audio_ref='x',
        assignment_run_id='s/run',created_graph_version='g',original_assignment_evidence={'scores_status':'not_recorded'})
         for i,v in enumerate(['voice_10','voice_321','voice_321','voice_322'])]
    memories=[dict(memory_node_id='504',kind='semantic',clip_id=1,available_at=10,
                  raw_text='<voice_10> is Alice. <voice_321> may be Alice.',utterance_ids=['s/u0']),
              dict(memory_node_id='740',kind='semantic',clip_id=1,available_at=10,
                   raw_text='The woman seated on the right is Katrina.'),
              dict(memory_node_id='741',kind='episodic',clip_id=1,available_at=10,raw_text='<voice_321> speaks.')]
    replay=dict(session_id='s',source_graph_version='g',current_cutoff=10,observations=obs,
                memories=memories,source_gaps=[],graph={'nodes':[{'id':10,'type':'voice'}],'edges':[]})
    state=initial_state('s','g')
    return replay,state,build_evidence(replay,state)


def patch(packet,decisions):
    return dict(schema_version=1,session_id=packet['session_id'],base_graph_version=packet['base_graph_version'],
                evidence_cutoff_s=packet['current_cutoff'],decisions=decisions)


def merge(did='d1',voices=None,target='person_0',evidence=None):
    return dict(decision_id=did,op='merge_voice',voice_ids=voices or ['voice_10'],target_entity_id=target,
                evidence_ids=evidence or ['semantic_504'])


def test_all_operations_and_retrieval(tmp_path):
    replay,state,packet=fixture()
    decisions=[merge(),dict(decision_id='d2',op='set_name',entity_id='person_0',name='Alice',aliases=['Al'],evidence_ids=['semantic_504']),
        dict(decision_id='d3',op='reassign_utterances',utterance_ids=['s/u1'],from_voice_id='voice_321',target_entity_id='person_1',evidence_ids=['semantic_740']),
        dict(decision_id='d4',op='set_name',entity_id='person_1',name='Katrina',evidence_ids=['semantic_740']),
        dict(decision_id='d5',op='resolve_reference',memory_node_id=740,mention='The woman seated on the right',entity_id='person_1',evidence_ids=['semantic_740']),
        dict(decision_id='d6',op='revise_claim',memory_node_id=504,status='contradicted',replacement=None,evidence_ids=['semantic_740']),
        dict(decision_id='d7',op='defer',target_ids=['voice_322'],reason='Insufficient evidence')]
    path,report=publish(replay,tmp_path,state,packet,patch(packet,decisions))
    assert not report['rejected']
    current=load_current(tmp_path,'s')
    assert current['assignments']=={'s/u0':'person_0','s/u1':'person_1'}
    graph,index=read(path/'graph.json'),read(path/'retrieval.json')
    assert graph['nodes']==replay['graph']['nodes']
    assert graph['graph_version']==index['graph_version']==current['graph_version']
    assert graph['canonical_memories'][2]['canonical_text']=='<voice_321> speaks.'
    assert graph['canonical_memories'][0]['raw_text']==replay['memories'][0]['raw_text']
    assert '504' not in index['document_ids']
    assert search(index,'Katrina',HashEmbedder())[0][0]=='740'
    assert (path/'audit.md').exists()


@pytest.mark.parametrize('field,value',[('session_id','other'),('base_graph_version','stale'),('evidence_cutoff_s',11)])
def test_envelope_rejection(field,value):
    _,state,packet=fixture(); p=patch(packet,[merge()]);p[field]=value
    with pytest.raises(ValueError): execute(state,packet,p)


def test_invalid_operations_isolated_and_atomic():
    _,state,packet=fixture()
    decisions=[merge('bad',['voice_10','voice_999']),merge('ok'),
               merge('conflict',['voice_10'],'person_1'),{'decision_id':'oops','op':'execute_python','code':'raise SystemExit'},
               dict(decision_id='badname',op='set_name',entity_id='person_0',name='Jake',evidence_ids=['semantic_504'])]
    out,report=execute(state,packet,patch(packet,decisions))
    assert len(report['accepted'])==1 and len(report['rejected'])==4
    assert set(out['entities'])=={'person_0'}
    assert not state['assignments']


def test_dependencies_duplicate_ids_and_unknown_evidence():
    _,state,packet=fixture()
    a=merge('a'); a['depends_on']=['missing']
    _,report=execute(state,packet,patch(packet,[a,merge('b'),merge('b'),merge('c',evidence=['unknown'])]))
    assert len(report['rejected'])==4


def test_future_and_foreign_evidence():
    for edits in ({'available_at':11},{'session_id':'other'}):
        _,state,packet=fixture();packet['evidence']['semantic_504'].update(edits)
        _,report=execute(state,packet,patch(packet,[merge()]))
        assert len(report['rejected'])==1


def test_cannot_link_and_mixed_reassignment():
    replay,state,packet=fixture()
    state['cannot_link']=[['voice_10','voice_322']]
    _,report=execute(state,packet,patch(packet,[merge(voices=['voice_10','voice_322'])]))
    assert report['rejected']
    packet['candidate_mixed_clusters']=['voice_321']
    d=dict(decision_id='split',op='reassign_utterances',utterance_ids=['s/u1'],from_voice_id='voice_321',
           target_entity_id='person_0',evidence_ids=['semantic_504'])
    out,report=execute(state,packet,patch(packet,[merge(voices=['voice_321']),d]))
    assert len(report['rejected'])==1
    assert out['assignments']=={'s/u1':'person_0'}


def test_moss_ambiguity_namespace_and_only_evidence():
    replay,state,packet=fixture()
    moss=dict(session_id='s',cutoff_s=10,run_id='moss_10',segments=[
        dict(start=0,end=.8,speaker='S1'),dict(start=.7,end=1,speaker='S2')])
    records,_,_=align(replay['observations'],moss,'s',10)
    assert records[0]['alignment_status']=='ambiguous'
    assert set(records[0]['overlaps'])=={'moss_10/S1','moss_10/S2'}
    packet=build_evidence(replay,state,moss)
    _,report=execute(state,packet,patch(packet,[merge(evidence=[records[0]['evidence_id']])]))
    assert report['rejected']
    moss['cutoff_s']=20
    with pytest.raises(ValueError):align(replay['observations'],moss,'s',10)
    assert parse_output('[0.0][S01]Hi[1.0]')[0]['speaker']=='S01'


def test_immutable_ledger_and_session(tmp_path):
    replay,_,_=fixture();ledger=ObservationLedger(tmp_path/'ledger.jsonl','s')
    ledger.append(replay['observations']);ledger.append(replay['observations'])
    assert len(ledger.load())==4
    changed=copy.deepcopy(replay['observations']);changed[0]['original_voice_id']='voice_99'
    with pytest.raises(ValueError):ledger.append(changed)
    with pytest.raises(ValueError):ObservationLedger(ledger.path,'other').load()


def test_publication_failure_and_tampering(tmp_path):
    replay,state,packet=fixture()
    class Broken:
        model_id='broken'
        def encode(self,texts): raise RuntimeError('embedding unavailable')
    with pytest.raises(RuntimeError):publish(replay,tmp_path,state,packet,patch(packet,[merge()]),Broken())
    assert load_current(tmp_path,'s') is None
    path,_=publish(replay,tmp_path,state,packet,patch(packet,[merge()]))
    with pytest.raises(ValueError):publish(replay,tmp_path,state,packet,patch(packet,[merge()]))
    (path/'retrieval.json').write_text('{}')
    with pytest.raises(ValueError):load_current(tmp_path,'s')


def test_online_log_before_mutation_and_tst(tmp_path):
    graph=SimpleNamespace(nodes={10:SimpleNamespace(type='voice',embeddings=[[1.,0.]])},audio_matching_threshold=.6,
                          search_voice_nodes=lambda a:[(10,1.)])
    logger=AssignmentLogger(tmp_path/'assignments.jsonl','s','CAM++/test')
    wrapper=LoggedVoiceGraph(graph,logger)
    wrapper.begin_observation('s/u0',1,'g',{'MAI':'hi'})
    assert wrapper.search_voice_nodes({'embeddings':[[1.,0.]]})==[(10,1.)]
    event=json.loads(logger.path.read_text())
    assert event['candidates'][0]['score']==1 and event['graph_version_before_assignment']=='g'
    with pytest.raises(ValueError):wrapper.search_voice_nodes({'embeddings':[[1.,0.]]})
    tst=AssignmentLogger(tmp_path/'tst.jsonl','s','TST/test',gallery={'enrollment_alice':'hash'})
    event=tst.record('s/u0',1,'g',[{'candidate_id':'enrollment_alice','score':.4,'eligible':False}],
                     'non_target',.6,method='TST')
    assert event['selected_candidate'] is None
    tst.gallery['other']='hash'
    with pytest.raises(ValueError):tst.record('s/u1',2,'g',[],None,.6,method='TST')


def test_metrics_and_schedule():
    replay,state,packet=fixture()
    state,_=execute(state,packet,patch(packet,[merge(voices=['voice_10','voice_322'])]))
    gold={o['utterance_id']:{'person_id':str(i),'name':'Alice'} for i,o in enumerate(replay['observations'])}
    result=evaluate(replay['observations'],state,gold)
    assert result['false_merge_rate']==1
    assert result['unresolved_speech_duration']==2
    assert result['correctly_attributed_speech_duration']==1
    assert result['identity_dependent_qa_accuracy'] is None
    assert schedule([{'absolute_start_seconds':0,'absolute_end_seconds':1190},
                     {'absolute_start_seconds':1190,'absolute_end_seconds':1210}])==[1190,1210]


def test_revised_claim_revokes_name_and_cannot_be_reused():
    _,state,packet=fixture()
    decisions=[merge(),dict(decision_id='name',op='set_name',entity_id='person_0',name='Alice',evidence_ids=['semantic_504']),
        dict(decision_id='revise',op='revise_claim',memory_node_id=504,status='contradicted',replacement=None,evidence_ids=['semantic_740']),
        merge('reuse',['voice_322'],'person_0')]
    out,report=execute(state,packet,patch(packet,decisions))
    assert out['entities']['person_0']['canonical_name'] is None
    assert len(report['rejected'])==1


def test_scheduler_final_and_new_observations_do_not_inherit():
    from consolidation.online import CommitScheduler
    s=CommitScheduler()
    assert not s.committed(1190)
    assert s.committed(1210)
    assert not s.committed(1210,final=True)
    assert s.committed(1250,final=True)


def test_deterministic_publishing_in_independent_roots(tmp_path):
    replay,state,packet=fixture()
    first,_=publish(replay,tmp_path/'a',state,packet,patch(packet,[merge()]))
    second,_=publish(replay,tmp_path/'b',state,packet,patch(packet,[merge()]))
    assert first.name==second.name
    assert read(first/'graph.json')==read(second/'graph.json')


def test_gallery_pinned_across_logger_restarts(tmp_path):
    path=tmp_path/'tst.jsonl'
    logger=AssignmentLogger(path,'s','tst',gallery={'a':'hash1'})
    logger.record('s/u0',1,'g',[{'candidate_id':'a','score':.7,'eligible':True}], 'a',.6,method='TST')
    logger=AssignmentLogger(path,'s','tst',gallery={'a':'hash2'})
    with pytest.raises(ValueError):
        logger.record('s/u1',2,'g',[{'candidate_id':'a','score':.7,'eligible':True}], 'a',.6,method='TST')


def test_online_wrapper_records_final_assignment(tmp_path):
    from consolidation.online import assign_observation
    class Graph:
        def __init__(self):
            self.nodes={};self.audio_matching_threshold=.6
        def search_voice_nodes(self,info):return []
        def add_voice_node(self,info):
            self.nodes[0]=SimpleNamespace(type='voice',metadata={'contents':info['contents']},embeddings=info['embeddings'])
            return 0
    graph=Graph()
    logger=AssignmentLogger(tmp_path/'scores.jsonl','s','cam-test')
    ledger=ObservationLedger(tmp_path/'observations.jsonl','s')
    audio={'start_time':'00:01','end_time':'00:02','asr':'MAI: hello','embedding':[1.,0.]}
    assert assign_observation(graph,logger,ledger,audio,'s',1,0,0,'audio','run')==0
    assert ledger.load()[0]['original_voice_id']=='voice_0'
    assert json.loads(logger.path.read_text())['reason']=='no_existing_candidates'
    with pytest.raises(ValueError):assign_observation(graph,logger,ledger,audio,'s',1,0,0,'audio','run')


def cluster(**overrides):
    value=dict(decision_id='default',op='assign_cluster',voice_ids=['voice_321'],
        target_entity_id='person_0',evidence_ids=['semantic_504'],confidence=.78,
        rationale='Cluster continuity supports Alice; explicit competing turn excluded.',
        excluded_utterance_ids=[])
    value.update(overrides)
    return value


def test_cluster_default_propagation_exceptions_and_provenance():
    replay,state,packet=fixture();packet['candidate_mixed_clusters']=['voice_321']
    exception=dict(decision_id='exception',op='reassign_utterances',utterance_ids=['s/u2'],
        from_voice_id='voice_321',target_entity_id='person_1',evidence_ids=['semantic_740'],
        confidence=.8,rationale='Contrary turn belongs to Katrina.')
    result,report=execute(state,packet,patch(packet,[cluster(excluded_utterance_ids=['s/u2']),exception]))
    assert not report['rejected']
    assert result['assignments']=={'s/u1':'person_0','s/u2':'person_1'}
    assert result['assignment_metadata']['s/u1']['confidence']==.78
    assert result['cluster_defaults']['voice_321']['excluded_utterance_ids']==['s/u2']
    assert result['assignment_history'][0]['previous_entity_id'] is None
    # A supported default propagates without an independent anchor on each utterance.
    result,report=execute(state,packet,patch(packet,[cluster()]))
    assert result['assignments']=={'s/u1':'person_0','s/u2':'person_0'}
    assert not report['rejected']


def test_cluster_default_cannot_overwrite_or_escape_scope():
    _,state,packet=fixture()
    state['assignments']['s/u1']='person_1';ensure=__import__('consolidation.entity_registry',fromlist=['ensure_entity'])
    ensure.ensure_entity(state,'person_1')
    for decision in [cluster(),cluster(excluded_utterance_ids=['s/u0']),cluster(confidence=1.1)]:
        result,report=execute(state,packet,patch(packet,[decision]))
        assert report['rejected'] and result['assignments']==state['assignments']
    state['assignments']={};state['cannot_link']=[['voice_321','voice_322']]
    _,report=execute(state,packet,patch(packet,[cluster(voice_ids=['voice_321','voice_322'])]))
    assert report['rejected']


def test_explicit_correction_records_previous_person():
    _,state,packet=fixture()
    first,_=execute(state,packet,patch(packet,[cluster()]))
    packet['previous_cutoff']=first['cutoff']
    correction=dict(decision_id='correct',op='reassign_utterances',utterance_ids=['s/u1'],
        from_voice_id='voice_321',target_entity_id='person_1',evidence_ids=['semantic_740'],
        confidence=.85,rationale='New contextual interpretation corrects prior assignment.')
    final,report=execute(first,packet,patch(packet,[correction]))
    assert not report['rejected']
    assert final['assignment_history'][-1]['previous_entity_id']=='person_0'
    assert first['assignments']['s/u1']=='person_0'
