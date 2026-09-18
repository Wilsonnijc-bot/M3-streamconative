from collections import Counter
from .common import dumps


def render(packet, state, report, retrieval):
    lines=[f"# Consolidation @ {packet['current_cutoff']/60:.3f} min",'',
        f"Session: `{packet['session_id']}`",f"Base: `{packet['base_graph_version']}`",'',
        '## Existing identities',dumps(packet['registry']),'','## MOSS diarization',
        'Not supplied; no MOSS evidence inferred.' if packet['moss'] is None else dumps({k:v for k,v in packet['moss'].items() if k!='segments'}),
        '', '## Voice/MOSS alignment', dumps(packet['voice_moss_summary']), '',
        '## Candidate merges',dumps(packet.get('candidate_merges',[])), '',
        '## Candidate mixed clusters',dumps(packet['candidate_mixed_clusters']), '',
        '## LLM decisions','']
    for d in report['accepted']:
        lines.extend([f"### {d['decision_id']}: {d['op']}", '```json',dumps(d),'```',''])
    lines.extend(['## Deferred conflicts and rejected operations',dumps(report['rejected']),'',
        '## Names',dumps({k:v['canonical_name'] for k,v in state['entities'].items()}),'',
        '## Graph changes',f"{len(state['entities'])} persistent people; {len(state['assignments'])} assigned observations.",
        'Raw graph nodes and original memory text retained.','',
        '## Retrieval indexes rebuilt',f"Dense model: `{retrieval['model_id']}`; {len(retrieval['document_ids'])} active memories.",
        'Dense vectors, lexical postings, entity mappings and Mandol references published in the same version.','',
        '## Historical evidence limitations',
        dumps(dict(Counter(o['original_assignment_evidence'].get('scores_status','recorded') for o in packet['observations']))),
        dumps(packet['source_gaps']),''])
    return '\n'.join(lines)
