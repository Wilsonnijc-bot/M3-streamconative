"""Metrics require independent observation-level gold, not semantic claims as truth."""
from collections import defaultdict


def evaluate(observations,state,gold,qa=None,retrieval=None,mixed_gold=None,mixed_pred=None):
    predicted=state['assignments']
    labeled=[o for o in observations if o['utterance_id'] in gold]
    totals=defaultdict(float)
    groups=defaultdict(set)
    predicted_groups=defaultdict(list)
    contingency=defaultdict(lambda:defaultdict(float))
    for o in labeled:
        u=o['utterance_id']; g=gold[u]['person_id']; p=predicted.get(u)
        duration=o['end_time']-o['start_time']
        totals['labeled_speech_duration']+=duration
        if p is None:
            totals['unresolved_speech_duration']+=duration
            continue
        groups[g].add(p)
        predicted_groups[p].append(g)
        contingency[p][g]+=duration
        name=state['entities'][p]['canonical_name']
        if gold[u].get('name') and name==gold[u]['name']:
            totals['correctly_named_speech_duration']+=duration
    # Best one-to-one assignment prevents separate fragments all counting as the same correct person.
    from itertools import permutations
    ps=list(contingency); gs=sorted({gold[o['utterance_id']]['person_id'] for o in labeled})
    if len(ps)<=8 and len(gs)<=8:
        n=max(len(ps),len(gs))
        rows=ps+[None]*(n-len(ps)); cols=gs+[None]*(n-len(gs))
        totals['correctly_attributed_speech_duration']=max((sum(contingency[p].get(g,0) if p and g else 0 for p,g in zip(rows,perm))
            for perm in permutations(cols)),default=0)
    else:
        try:
            from scipy.optimize import linear_sum_assignment
            import numpy as np
            matrix=np.array([[contingency[p].get(g,0) for g in gs] for p in ps])
            rows,cols=linear_sum_assignment(-matrix)
            totals['correctly_attributed_speech_duration']=float(matrix[rows,cols].sum())
        except ImportError:
            totals['correctly_attributed_speech_duration']=None
    total_pairs=false_pairs=0
    for labels in predicted_groups.values():
        for i,left in enumerate(labels):
            for right in labels[i+1:]:
                total_pairs+=1; false_pairs+=left!=right
    result=dict(totals)
    result.update(false_merge_rate=false_pairs/total_pairs if total_pairs else None,
        identity_fragmentation=sum(max(0,len(p)-1) for p in groups.values()),
        labeled_observations=len(labeled), unlabeled_observations=len(observations)-len(labeled),
        identity_dependent_qa_accuracy=sum(qa)/len(qa) if qa else None,
        retrieval_accuracy=sum(retrieval)/len(retrieval) if retrieval else None)
    if mixed_gold is not None:
        truth,pred=set(mixed_gold),set(mixed_pred or [])
        result['mixed_cluster_precision']=len(truth&pred)/len(pred) if pred else None
        result['mixed_cluster_recall']=len(truth&pred)/len(truth) if truth else None
    else:
        result['mixed_cluster_precision']=result['mixed_cluster_recall']=None
    for key in ('unresolved_speech_duration','correctly_named_speech_duration','labeled_speech_duration'):
        result.setdefault(key,0.0)
    return result


def compare_variants(observations, variants, gold, **metrics):
    required={'baseline_m3','moss_only','semantic_llm','moss_semantic_llm'}
    unknown=set(variants)-required
    if unknown:
        raise ValueError('unknown evaluation variants: '+str(sorted(unknown)))
    return {name:evaluate(observations,variants[name],gold,**metrics) if name in variants else
            {'status':'not_run'} for name in sorted(required)}


def baseline_state(observations,session_id):
    """Baseline M3 treats each original voice as a separate identity, without names."""
    from .entity_registry import initial_state,ensure_entity,refresh_registry
    state=initial_state(session_id,'baseline')
    for o in observations:
        if o['session_id']!=session_id:
            raise ValueError('baseline session mismatch')
        if o['original_voice_id'] is not None:
            eid=o['original_voice_id']
            ensure_entity(state,eid)
            state['assignments'][o['utterance_id']]=eid
    refresh_registry(state,observations)
    return state
