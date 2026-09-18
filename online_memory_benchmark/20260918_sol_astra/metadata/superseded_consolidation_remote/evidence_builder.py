from copy import deepcopy
from .common import digest
from .moss_alignment import align


def build_evidence(replay, state, moss=None, assignments=()):
    session, cutoff = replay['session_id'], replay['current_cutoff']
    if state['session_id'] != session or state['cutoff'] > cutoff:
        raise ValueError('state namespace or chronology mismatch')
    alignments, summaries, mixed = align(replay['observations'], moss, session, cutoff)
    evidence = {}
    observations = deepcopy(replay['observations'])
    for o in observations:
        if o['session_id']!=session or o['end_time']>cutoff:
            raise ValueError('future/foreign observation')
        o['current_entity_id'] = state['assignments'].get(o['utterance_id'])
        evidence[o['utterance_id']] = dict(kind='observation', session_id=session, available_at=o['end_time'])
    if not set(state['assignments']) <= {o['utterance_id'] for o in observations}:
        raise ValueError('current evidence is missing previously assigned observations')
    memories = deepcopy(replay['memories'])
    for m in memories:
        if m['available_at']>cutoff:
            raise ValueError('future memory')
        m['evidence_id'] = m['kind']+'_'+m['memory_node_id']
        evidence[m['evidence_id']] = dict(m, session_id=session)
    for a in alignments:
        evidence[a['evidence_id']] = a
    speaker_voices = {}
    for a in alignments:
        if a['alignment_status']=='aligned' and a['original_voice_id']:
            speaker_voices.setdefault(a['speaker'],set()).add(a['original_voice_id'])
    candidate_merges = [dict(moss_speaker=speaker,voice_ids=sorted(voices),status='hypothesis_only')
                        for speaker,voices in sorted(speaker_voices.items()) if len(voices)>1]
    historical = []
    for a in assignments:
        if a['session_id']!=session or a['available_at']>cutoff:
            raise ValueError('future/foreign assignment evidence')
        historical.append(deepcopy(a))
        evidence[a['evidence_id']] = a
    clusters=[]
    for voice in sorted({o['original_voice_id'] for o in observations if o['original_voice_id']}):
        members=[o for o in observations if o['original_voice_id']==voice]
        clusters.append(dict(voice_id=voice, observation_count=len(members),
            utterance_ids=[o['utterance_id'] for o in members],
            start_time=min(o['start_time'] for o in members), end_time=max(o['end_time'] for o in members),
            current_entities=sorted({o['current_entity_id'] for o in members if o['current_entity_id']}),
            unresolved_count=sum(o['current_entity_id'] is None for o in members),
            moss_summary=summaries.get(voice,{}), possible_mixed=voice in mixed))
    return dict(previous_execution=deepcopy(state["decision_history"][-1] if state["decision_history"] else None),
        cluster_inventory=clusters, cluster_defaults=deepcopy(state.get('cluster_defaults',{})),
        assignment_metadata=deepcopy(state.get('assignment_metadata',{})),
        coverage=dict(total=len(observations),assigned=len(state['assignments']),
            unresolved=len(observations)-len(state['assignments'])),
        schema_version=1, session_id=session, base_graph_version=state['graph_version'],
        source_graph_version=replay['source_graph_version'], previous_cutoff=state['cutoff'],
        current_cutoff=cutoff, registry=deepcopy(state['entities']), observations=observations,
        voice_ids=['voice_'+str(n['id']) for n in replay['graph']['nodes'] if n['type']=='voice'],
        original_assignments=historical, moss=deepcopy(moss), moss_alignments=alignments,
        voice_moss_summary=summaries, candidate_merges=candidate_merges, candidate_mixed_clusters=mixed, memories=memories,
        evidence=evidence, cannot_link=deepcopy(state['cannot_link']), source_gaps=replay['source_gaps'])
