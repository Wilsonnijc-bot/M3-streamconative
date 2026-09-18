from copy import deepcopy


def initial_state(session_id, graph_version):
    return dict(session_id=session_id, graph_version=graph_version, cutoff=0,
                consolidation_index=0, entities={}, assignments={}, references={}, claims={},
                cannot_link=[], decision_history=[])


def ensure_entity(state, entity):
    if entity not in state['entities']:
        state['entities'][entity] = dict(voice_ids=[], utterance_ids=[], canonical_name=None,
            aliases=[], name_evidence=[], created_at_consolidation=state['consolidation_index'],
            updated_at_consolidation=state['consolidation_index'])
    return state['entities'][entity]


def refresh_registry(state, observations):
    lookup = {o['utterance_id']:o for o in observations}
    for eid, entity in state['entities'].items():
        entity['utterance_ids'] = sorted(u for u,e in state['assignments'].items() if e==eid)
        entity['voice_ids'] = sorted({lookup[u].get('original_voice_id') for u in entity['utterance_ids']
                                      if lookup[u].get('original_voice_id') is not None})
