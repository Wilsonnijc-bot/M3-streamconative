from copy import deepcopy
import json

import pytest

from consolidation.common import read
from consolidation.evidence_builder import build_evidence
from consolidation.entity_registry import initial_state
from consolidation.llm_consolidator import request_payload, propose
from consolidation.patch_executor import execute
from consolidation.prompt_packet import build_prompt_packet, prepare_prompt, PromptBudgetError, byte_size
from .test_system import fixture, patch, cluster


def history_packet(windows=3):
    state = initial_state('s', 'g')
    state.update(cutoff=(windows - 1)*1200, cutoff_clip=windows - 1)
    state['entities'] = {
        'person_0': dict(native_character_id='character_0', canonical_name='Alice', aliases=[],
                         voice_ids=['voice_0'], name_evidence=['semantic_1']),
        'person_1': dict(native_character_id='character_1', canonical_name=None, aliases=[],
                         voice_ids=['voice_1'], name_evidence=[])}
    obs, memories = [], []
    for clip in range(1, windows + 1):
        for speaker in (0, 1):
            uid = f's/u{clip}_{speaker}'
            obs.append(dict(utterance_id=uid, session_id='s', clip_id=clip,
                start_time=(clip - 1)*1200 + speaker*10, end_time=(clip - 1)*1200 + speaker*10 + 2,
                original_voice_id=f'voice_{speaker}', original_transcript='same words',
                transcripts={'MAI': 'same words', 'Deepgram': 'same words'},
                audio_ref='/private/recording.wav', created_graph_version='internal-hash',
                original_assignment_evidence=dict(source_graph='/private/graph.pkl', scores_status='not_recorded')))
            if clip < windows:
                state['assignments'][uid] = f'person_{speaker}'
        memories.append(dict(memory_node_id=str(clip), kind='semantic', clip_id=clip,
            available_at=clip*1200, raw_text='<voice_0> is Alice.\n<voice_1> replies.',
            raw_contents=['<voice_0> is Alice.', '<voice_1> replies.']))
    replay = dict(session_id='s', current_cutoff=windows*1200, source_graph_version='g',
        current_cutoff_clip=windows, observations=obs, memories=memories, graph={'nodes': []}, source_gaps=[])
    moss = dict(session_id='s', start_s=(windows-1)*1200, cutoff_s=windows*1200, run_id=f'run_{windows}', segments=[
        dict(start=o['start_time'], end=o['end_time'], speaker='S'+o['original_voice_id'][-1], text='same words')
        for o in obs if o['clip_id']==windows])
    return replay, state, build_evidence(replay, state, moss)


def test_allowlist_exact_texts_and_no_duplicate_records(tmp_path):
    _, _, packet = history_packet()
    packet['previous_execution'] = {'accepted': [{'rationale': 'OLD_DECISION_PROSE'}]}
    packet['assignment_metadata'] = {'s/u1_0': {'rationale': 'OLD_DECISION_PROSE'}}
    view = prepare_prompt(packet, tmp_path)
    encoded = json.dumps(view)
    assert '/private/' not in encoded and 'internal-hash' not in encoded
    assert 'OLD_DECISION_PROSE' not in encoded
    assert 'evidence' not in view and 'cluster_defaults' not in view
    assert len({o['utterance_id'] for o in view['observations']}) == len(view['observations'])
    for o in view['observations']:
        assert o['transcripts'] == [{'text': 'same words', 'sources': ['Deepgram', 'MAI']}]
        assert o['quality']['scores_status'] == 'not_recorded'
        assert 'original_transcript' not in o
    assert all(m['contents'] == ['<voice_0> is Alice.', '<voice_1> replies.'] for m in view['memories'])
    assert all('raw_text' not in m for m in view['memories'])
    assert read(tmp_path/'prompt_packet.json') == view
    assert read(tmp_path/'prompt_scope.json') == packet['_execution_scope']
    assert read(tmp_path/'prompt_size.json')['bytes'] == byte_size(view)
    assert packet['observations'][0]['audio_ref'] == '/private/recording.wav'


@pytest.mark.parametrize('windows', [1, 2, 3])
def test_window_boundaries_returning_characters_and_current_moss(windows):
    _, _, packet = history_packet(windows)
    view, scope, report = build_prompt_packet(packet)
    assert scope['new_observation_ids'] == [f's/u{windows}_0', f's/u{windows}_1']
    assert view['characters']['person_1']['canonical_name'] is None
    assert view['characters']['person_1']['native_character_id'] == 'character_1'
    assert view['moss']['run_id'] == f'run_{windows}'
    assert all(f'/run_{windows}' in a['evidence_id'] for a in view['moss']['alignments'])
    assert report['historical_bytes'] <= report['history_limit_bytes']
    assert {m['memory_node_id'] for m in view['memories']} >= {str(windows)}
    assert all(int(mid) <= windows for mid in scope['memory_ids'])


def test_new_defaults_and_explicit_historical_corrections():
    _, state, packet = history_packet(10)
    view = prepare_prompt(packet)
    scope = packet['_execution_scope']
    old = next(u for u in scope['historical_observation_ids'] if u.endswith('_0'))
    hidden = next(o['utterance_id'] for o in packet['observations']
                  if o['clip_id'] < 10 and o['utterance_id'] not in scope['historical_observation_ids'])
    decisions = [cluster(voice_ids=['voice_0'], evidence_ids=['s/u10_0']),
        dict(decision_id='correct', op='reassign_utterances', from_voice_id='voice_0',
             utterance_ids=[old], target_entity_id='person_1', evidence_ids=['s/u10_0']),
        dict(decision_id='hidden', op='reassign_utterances', from_voice_id='voice_'+hidden[-1],
             utterance_ids=[hidden], target_entity_id='person_1', evidence_ids=['s/u10_0']),
        dict(decision_id='hidden_support', op='set_name', entity_id='person_1', name='Alice', evidence_ids=[hidden])]
    result, report = execute(state, packet, patch(packet, decisions))
    assert len(report['accepted']) == 2 and len(report['rejected']) == 2
    assert result['assignments']['s/u10_0'] == 'person_0'
    assert result['assignments'][old] == 'person_1'
    assert result['assignments'][hidden] == state['assignments'][hidden]
    assert result['assignments']['s/u1_0'] == state['assignments']['s/u1_0'] or old == 's/u1_0'
    assert view['previous_cutoff_clip'] == 9


def test_cluster_default_never_reassigns_old_voice_members():
    _, state, packet = history_packet()
    prepare_prompt(packet)
    result, report = execute(state, packet, patch(packet, [cluster(voice_ids=['voice_0'],
        target_entity_id='person_1', evidence_ids=['s/u3_0'])]))
    assert not report['rejected']
    assert result['assignments']['s/u3_0'] == 'person_1'
    assert result['assignments']['s/u1_0'] == 'person_0'
    assert result['assignments']['s/u2_0'] == 'person_0'


def test_scoped_memory_corrections_and_exact_occurrences():
    _, state, packet = history_packet(10)
    prepare_prompt(packet)
    visible = packet['_execution_scope']['memory_ids']
    hidden = next(str(i) for i in range(1, 10) if str(i) not in visible)
    resolve = dict(decision_id='ref', op='resolve_reference', memory_node_id='10',
        mention='<voice_1>', content_index=1, start=0, end=9,
        entity_id='person_1', evidence_ids=['s/u10_1'])
    result, report = execute(state, packet, patch(packet, [resolve,
        dict(resolve, decision_id='hidden_ref', memory_node_id=hidden),
        dict(decision_id='revise', op='revise_claim', memory_node_id='1', status='contradicted',
             replacement=None, evidence_ids=['s/u10_0'])]))
    assert len(report['accepted']) == 2
    assert report['rejected'][0]['reason'] == 'memory is outside prompt scope'
    assert result['entities']['person_0']['canonical_name'] is None
    assert result['references']['10::<voice_1>::1:0:9']['entity_id'] == 'person_1'


def test_history_is_deterministic_bounded_and_never_truncated():
    _, _, packet = history_packet(30)
    first = build_prompt_packet(packet, history_bytes=2500)
    shuffled = deepcopy(packet)
    shuffled['observations'].reverse(); shuffled['memories'].reverse()
    assert first == build_prompt_packet(shuffled, history_bytes=2500)
    assert first[2]['historical_bytes'] <= 2500
    assert len(first[1]['new_observation_ids']) == 2
    assert all(t['text'] == 'same words' for o in first[0]['observations'] for t in o['transcripts'])
    packet['observations'][0]['transcripts'] = {'MAI': 'x'*10000}
    view, scope, report = build_prompt_packet(packet, history_bytes=2500)
    assert 's/u1_0' not in scope['historical_observation_ids']
    assert report['historical_bytes'] <= 2500


def test_fixed_population_history_does_not_grow_with_session():
    sizes = []
    for windows in (10, 30, 60):
        _, _, packet = history_packet(windows)
        view, scope, report = build_prompt_packet(packet)
        sizes.append(report['bytes'])
        assert len(scope['historical_observation_ids']) <= 4
        assert len(view['memories']) <= 5
    assert max(sizes) - min(sizes) < 1000


def test_budget_fails_before_network_and_saves_diagnostics(tmp_path, monkeypatch):
    _, _, packet = history_packet()
    monkeypatch.setenv('CONSOLIDATION_PACKET_BYTES', '100')
    def forbidden(*args, **kwargs):
        pytest.fail('oversized packet reached network')
    monkeypatch.setattr('urllib.request.urlopen', forbidden)
    with pytest.raises(PromptBudgetError) as error:
        propose(packet, tmp_path, 'model', 'http://localhost/v1')
    assert error.value.report == read(tmp_path/'prompt_size.json')
    assert read(tmp_path/'prompt_packet.json')['observations']
    assert '_execution_scope' not in packet


def test_missing_moss_and_boundary_disagreement():
    replay, state, _ = history_packet()
    packet = build_evidence(replay, state)
    assert prepare_prompt(packet)['moss'] == {'run_id': None, 'segments': {}, 'alignments': []}
    packet['previous_cutoff_clip'] = 1
    with pytest.raises(ValueError, match='boundary disagrees'):
        prepare_prompt(packet)


def test_boundary_context_asr_variants_and_new_moss_labels():
    replay, state, _ = history_packet()
    replay['observations'][2].update(start_time=2395, end_time=2399)
    replay['observations'][4].update(start_time=2398, end_time=2402,
        transcripts={'MAI': 'same words', 'Deepgram': 'different words'})
    moss = dict(session_id='s', start_s=2400,run_id='new_run_with_relabelled_speakers', cutoff_s=3600,
        segments=[dict(start=2400, end=2402, speaker='S99', text='boundary speech'),
                  dict(start=2400, end=2401, speaker='S17', text='overlap')],
        anomalies=[dict(action='bounded_to_input_audio', raw_segment={'text': 'RAW_ANOMALY'})],
        runtime={'path': '/private/model'}, audio_sha256='PRIVATE_HASH')
    packet = build_evidence(replay, state, moss)
    view, scope, _ = build_prompt_packet(packet)
    assert 's/u3_0' in scope['new_observation_ids']
    assert 's/u2_0' in scope['historical_observation_ids']
    observation = next(o for o in view['observations'] if o['utterance_id'] == 's/u3_0')
    assert len(observation['transcripts']) == 2
    assert {s['speaker'] for s in view['moss']['segments'].values()} == {'S99', 'S17'}
    assert all(a['alignment_status'] == 'ambiguous' for a in view['moss']['alignments']
               if a['utterance_id'] in ('s/u2_0', 's/u3_0'))
    assert all(a['utterance_id'] != 's/u2_0' for a in view['moss']['alignments'])
    assert view['moss']['quality_warnings'] == {'bounded_to_input_audio': 1}
    assert 'RAW_ANOMALY' not in json.dumps(view) and 'PRIVATE_HASH' not in json.dumps(view)


def test_historical_budget_counts_assignment_and_moss_dependencies():
    _, _, packet = history_packet()
    packet['original_assignments'] = [dict(evidence_id='assignment/s/u1_0', utterance_id='s/u1_0',
        candidates=[dict(candidate_id='voice_'+str(i), score=.5, eligible=False) for i in range(1000)])]
    view, scope, report = build_prompt_packet(packet, history_bytes=2500)
    assert 's/u1_0' not in scope['historical_observation_ids']
    assert not view['assignment_evidence']
    assert report['historical_bytes'] <= 2500


def test_shared_request_builder_saves_only_compact_user_input(tmp_path):
    _, _, packet = fixture()
    request = request_payload(packet, 'test', tmp_path)
    assert json.loads(request['messages'][1]['content']) == read(tmp_path/'prompt_packet.json')
    assert set(packet['_execution_scope']['new_observation_ids']) == {'s/u0', 's/u1', 's/u2', 's/u3'}
