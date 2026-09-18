"""Deterministic, copy-on-write patch execution. No model-supplied code is executed."""
from collections import Counter
from copy import deepcopy
from .common import dumps
from .schema import validate_envelope, validate_decision
from .entity_registry import ensure_entity, refresh_registry


def execute(state, packet, patch, *, scope=None):
    validate_envelope(patch)
    dumps(patch)  # rejects NaN/Infinity even when a JSON parser accepted them
    if patch['session_id'] != state['session_id'] or packet['session_id'] != state['session_id']:
        raise ValueError('session mismatch')
    if patch['base_graph_version'] != state['graph_version'] or packet['base_graph_version'] != state['graph_version']:
        raise ValueError('stale graph version')
    if patch['evidence_cutoff_s'] != packet['current_cutoff'] or packet['previous_cutoff'] != state['cutoff']:
        raise ValueError('cutoff mismatch')
    observations = {o['utterance_id']:o for o in packet['observations']}
    memories = {m['memory_node_id']:m for m in packet['memories']}
    voices = ({o['original_voice_id'] for o in observations.values()} - {None}) | set(packet.get('voice_ids',[]))
    scope = scope if scope is not None else packet.get('_execution_scope')
    if scope is not None:
        new_observations = set(scope['new_observation_ids'])
        visible_observations = new_observations | set(scope['historical_observation_ids'])
        visible_memories = set(scope['memory_ids'])
        visible_evidence = set(scope['evidence_ids'])
        voices &= set(scope['voice_ids'])
    result = deepcopy(state)
    result['consolidation_index'] += 1
    accepted, rejected, assigned_this_patch = [], [], {}
    references_this_patch = {}
    ids = Counter(d.get('decision_id') for d in patch['decisions'] if isinstance(d,dict))
    for index, decision in enumerate(patch['decisions']):
        candidate = deepcopy(result)
        try:
            validate_decision(decision)
            did, op = decision['decision_id'], decision['op']
            if ids[did] != 1:
                raise ValueError('duplicate decision_id')
            if not set(decision.get('depends_on',[])) <= {d['decision_id'] for d in accepted}:
                raise ValueError('unsatisfied dependency')
            evidence_ids = decision.get('evidence_ids', [])
            if scope is not None:
                if not set(evidence_ids) <= visible_evidence:
                    raise ValueError('evidence is outside prompt scope')
                if 'memory_node_id' in decision and str(decision['memory_node_id']) not in visible_memories:
                    raise ValueError('memory is outside prompt scope')
                if not set(decision.get('utterance_ids', [])) <= visible_observations:
                    raise ValueError('observation is outside prompt scope')
            evidence = []
            for eid in evidence_ids:
                if eid not in packet['evidence']:
                    raise ValueError('unknown evidence: '+eid)
                record = packet['evidence'][eid]
                if record['session_id'] != state['session_id'] or record['available_at'] > packet['current_cutoff']:
                    raise ValueError('foreign or future evidence')
                if record['kind']=='semantic' and str(record.get('memory_node_id')) in candidate['claims']:
                    raise ValueError('evidence claim has been contradicted or superseded')
                evidence.append(record)
            touched = []
            if op in ('merge_voice','assign_cluster','reassign_utterances'):
                target = decision['target_entity_id']
                if op in ('merge_voice','assign_cluster'):
                    if not set(decision['voice_ids']) <= voices:
                        raise ValueError('unknown voice')
                    if op=='merge_voice' and set(decision['voice_ids']) & set(packet['candidate_mixed_clusters']):
                        raise ValueError('mixed voice needs observation-level reassignment')
                    if all(e['kind']=='moss_alignment' for e in evidence):
                        raise ValueError('MOSS alone is insufficient for a merge')
                    touched = [u for u,o in observations.items() if o['original_voice_id'] in decision['voice_ids']]
                    if scope is not None:
                        touched = [u for u in touched if u in new_observations]
                    if op=='assign_cluster':
                        excluded=set(decision['excluded_utterance_ids'])
                        if not excluded <= set(touched):
                            raise ValueError('cluster exception outside reviewed voices')
                        touched=[u for u in touched if u not in excluded]
                    if not touched:
                        raise ValueError('no reviewed observations for merge')
                    if any(candidate['assignments'].get(u, target)!=target for u in touched):
                        raise ValueError('merge would overwrite an existing identity; use reassign_utterances')
                else:
                    touched = decision['utterance_ids']
                    if decision['from_voice_id'] not in voices:
                        raise ValueError('unknown source voice')
                    for uid in touched:
                        if uid not in observations or observations[uid]['original_voice_id'] != decision['from_voice_id']:
                            raise ValueError('utterance/source mismatch')
                for uid in touched:
                    if uid in assigned_this_patch and assigned_this_patch[uid]!=target:
                        raise ValueError('conflicting utterance assignment within patch')
                ensure_entity(candidate, target)
                for uid in touched:
                    previous=candidate['assignments'].get(uid)
                    candidate.setdefault('assignment_history',[]).append(dict(
                        utterance_id=uid, previous_entity_id=previous, entity_id=target,
                        decision_id=did, consolidation_index=candidate['consolidation_index'],
                        evidence_ids=evidence_ids, confidence=decision.get('confidence'),
                        rationale=decision.get('rationale'), scope=op))
                    candidate.setdefault('assignment_metadata',{})[uid]=dict(
                        confidence=decision.get('confidence'), rationale=decision.get('rationale'),
                        evidence_ids=evidence_ids, decision_id=did, scope=op)
                    candidate['assignments'][uid] = target
                if op=='assign_cluster':
                    for voice in decision['voice_ids']:
                        candidate.setdefault('cluster_defaults',{})[voice]=dict(
                            entity_id=target, confidence=decision['confidence'], rationale=decision['rationale'],
                            evidence_ids=evidence_ids, cutoff_s=packet['current_cutoff'],
                            excluded_utterance_ids=decision['excluded_utterance_ids'], decision_id=did)

                refresh_registry(candidate, list(observations.values()))
                for left,right in candidate['cannot_link']:
                    def entities_for(key):
                        if key in candidate['entities']:
                            return {key}
                        if key in observations:
                            return {candidate['assignments'].get(key)} - {None}
                        return {candidate['assignments'][u] for u,o in observations.items()
                                if o['original_voice_id']==key and u in candidate['assignments']}
                    if entities_for(left) & entities_for(right):
                        raise ValueError('known identity contradiction')
                candidate['entities'][target]['updated_at_consolidation']=candidate['consolidation_index']
            elif op == 'set_name':
                entity = candidate['entities'].get(decision['entity_id'])
                if entity is None:
                    raise ValueError('entity must be created before naming')
                # Grounding is still reconciler judgment; require at least explicit name-bearing text.
                name = decision['name'].strip()
                if not name or not any(e['kind'] in ('semantic','episodic') and name.casefold() in e.get('raw_text','').casefold() for e in evidence):
                    raise ValueError('name lacks semantic/event text support')
                if entity['canonical_name'] and entity['canonical_name'] != name:
                    old_evidence = entity['name_evidence']
                    retired = {m['evidence_id'] for m in packet['memories']
                               if candidate['claims'].get(m['memory_node_id'],{}).get('status') in ('contradicted','superseded')}
                    if not old_evidence or not set(old_evidence)<=retired:
                        raise ValueError('existing name support must be revised before renaming')
                entity.update(canonical_name=name, aliases=decision.get('aliases',[]), name_evidence=evidence_ids,
                              updated_at_consolidation=candidate['consolidation_index'])
            elif op == 'resolve_reference':
                mid = str(decision['memory_node_id'])
                if mid not in memories or decision['entity_id'] not in candidate['entities']:
                    raise ValueError('unknown memory/entity')
                mention=decision['mention']
                if mention not in memories[mid]['raw_text']:
                    raise ValueError('mention not found')
                key=mid+'::'+mention
                occurrence = {k:decision[k] for k in ('content_index','start','end') if k in decision}
                if occurrence:
                    contents = memories[mid].get('raw_contents', [memories[mid]['raw_text']])
                    i, start, end = occurrence['content_index'], occurrence['start'], occurrence['end']
                    if i >= len(contents) or start >= end or contents[i][start:end] != mention:
                        raise ValueError('invalid memory reference occurrence')
                    key += '::'+str(i)+':'+str(start)+':'+str(end)
                existing=references_this_patch.get(key)
                if existing and existing!=decision['entity_id']:
                    raise ValueError('conflicting reference resolution')
                for prior in accepted:
                    if (prior['op'] == 'resolve_reference' and str(prior['memory_node_id']) == mid
                            and prior['mention'] == mention and prior['entity_id'] != decision['entity_id']
                            and (not occurrence or 'content_index' not in prior or
                                 all(prior[k] == v for k, v in occurrence.items()))):
                        raise ValueError('conflicting reference resolution')
                # A broad correction replaces prior occurrence resolutions of this mention.
                for previous_key, reference in list(candidate['references'].items()):
                    if (str(reference['memory_node_id']) == mid and reference['mention'] == mention
                            and (not occurrence or all(reference.get(k) == v for k, v in occurrence.items()))):
                        del candidate['references'][previous_key]
                candidate['references'][key]=dict(memory_node_id=mid, mention=mention,
                    entity_id=decision['entity_id'], evidence_ids=evidence_ids, **occurrence)
            elif op == 'revise_claim':
                mid=str(decision['memory_node_id'])
                if mid not in memories or memories[mid]['kind']!='semantic':
                    raise ValueError('revise_claim requires a semantic memory')
                candidate['claims'][mid]={k:decision[k] for k in ('status','replacement','evidence_ids')}
                retired=memories[mid]['evidence_id']
                for entity in candidate['entities'].values():
                    if retired in entity['name_evidence']:
                        entity['name_evidence']=[e for e in entity['name_evidence'] if e!=retired]
                        if not entity['name_evidence']:
                            entity['canonical_name']=None
                            entity['aliases']=[]
            elif op == 'defer':
                known = voices | set(observations) | set(candidate['entities']) | set(memories)
                if scope is not None:
                    known = voices | visible_observations | set(candidate['entities']) | visible_memories
                if not set(decision['target_ids']) <= known:
                    raise ValueError('unknown deferred target')
            result=candidate
            accepted.append(deepcopy(decision))
            if op=='resolve_reference':
                references_this_patch[key]=decision['entity_id']
            for uid in touched:
                assigned_this_patch[uid]=decision['target_entity_id']
        except (ValueError, KeyError, TypeError) as error:
            rejected.append(dict(index=index, decision=decision, reason=str(error)))
        except Exception as error:
            from jsonschema.exceptions import ValidationError
            if not isinstance(error, ValidationError):
                raise
            rejected.append(dict(index=index, decision=decision, reason=error.message))
    result['cutoff']=packet['current_cutoff']
    result['cutoff_clip'] = packet.get('current_cutoff_clip')
    result['decision_history'].append(dict(accepted=accepted,rejected=rejected,cutoff=result['cutoff']))
    return result, {'accepted':accepted,'rejected':rejected}
