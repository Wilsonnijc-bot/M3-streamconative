"""Complete readable consolidated graph: registry, source nodes, memories and edges."""
from collections import Counter,defaultdict
from html import escape
from .common import dumps


def safe(value):
    return escape(str(value)).replace('|','&#124;').replace('\n','<br>')


def render_graph(graph,state,packet,execution):
    observations=packet['observations']
    by_voice=defaultdict(list)
    for o in observations:by_voice[o['original_voice_id']].append(o)
    lines=[f"# Updated memory graph — {packet['current_cutoff']:.2f} seconds",'',
        f"Session: `{state['session_id']}`",f"Published graph version: `{state['graph_version']}`",'',
        'This is the complete consolidated graph view for this checkpoint. Original source nodes and edges remain present.',
        'Canonical identities are model-supported interpretations. A source voice listed under a person may be only partially assigned.',
        '', '## Graph summary','',
        f"- Original nodes: {len(graph['nodes'])}; original edges: {len(graph['edges'])}.",
        f"- Canonical people: {len(state['entities'])}; observation-to-person edges: {len(state['assignments'])}.",
        f"- Assigned observations: {len(state['assignments'])}/{len(observations)}.",
        f"- Accepted decisions: {len(execution['accepted'])}; rejected decisions: {len(execution['rejected'])}.",
        '', '## Canonical people','']
    for eid,entity in state['entities'].items():
        lines += [f'<a id="{eid}"></a>',f"### {eid} — {safe(entity['canonical_name'] or 'unnamed')}",'',
            '**Aliases:** '+safe(', '.join(entity['aliases']) or 'none'),
            '**Source voices (observation-level provenance):** '+', '.join(f'`{v}`' for v in entity['voice_ids']),
            '**Name evidence:** '+', '.join(f'`{v}`' for v in entity['name_evidence']),
            f"**Created / updated consolidation:** {entity['created_at_consolidation']} / {entity['updated_at_consolidation']}",'']
    lines += ['## Cluster defaults','',
        'Defaults cover only the reviewed prefix. Exceptions remain explicit; later evidence can correct assignments.','',
        '| Voice | Person | Confidence | Exceptions | Rationale / evidence |',
        '| --- | --- | --- | --- | --- |']
    for voice,default in state.get('cluster_defaults',{}).items():
        lines.append(f"| {voice} | {default['entity_id']} | {default['confidence']} | {safe(default['excluded_utterance_ids'])} | {safe(default['rationale'])}<br>{safe(default['evidence_ids'])} |")
    lines.append('')
    lines += ['## Speech observations and identity edges','',
        'Original voice and transcripts are immutable. Unresolved observations retain their original voice reference.','',
        '| Utterance | Time (s) | Original voice | Canonical entity | Confidence / evidence / reason | Original transcripts |',
        '| --- | --- | --- | --- | --- | --- |']
    for o in observations:
        uid=o['utterance_id'];eid=state['assignments'].get(uid)
        transcript='<br>'.join(safe(source)+': '+safe(text) for source,text in o['transcripts'].items())
        entity=f'[{eid}](#{eid})' if eid else 'unresolved'
        provenance=safe(state.get('assignment_metadata',{}).get(uid, 'legacy assignment; see decision history')) if eid else ''
        lines.append(f"| `{uid}` | {o['start_time']:.2f}–{o['end_time']:.2f} | {o['original_voice_id'] or 'ambiguous original assignment'} | {entity} | {provenance} | {transcript} |")
    lines += ['','## Original voice nodes','',
        'These nodes were retained, not physically merged. The counts below show exactly how much of each voice was assigned.','']
    for node in graph['nodes']:
        if node['type']!='voice':continue
        vid='voice_'+str(node['id']);obs=by_voice[vid]
        assignments=Counter(state['assignments'].get(o['utterance_id'],'unresolved') for o in obs)
        lines += [f'<a id="node-{node["id"]}"></a>',f'### {vid}','',
                  '**Observation assignments:** '+safe(dict(assignments)),
                  '**Original transcript contents:**','']
        lines.extend('- '+safe(text) for text in node['metadata'].get('contents',[]))
        lines.append('')
    lines += ['## Canonical semantic and episodic memory','',
        'Every memory node is included. When canonical text changes, the original is shown below it.','']
    for m in graph['canonical_memories']:
        mid=m['memory_node_id']
        lines += [f'<a id="node-{mid}"></a>',f"### {m['kind']} {mid} · clip {m['clip_id']}",'',
                  safe(m['canonical_text']),'']
        if m['canonical_text']!=m['raw_text']:
            lines += ['**Original:** '+safe(m['raw_text']),'']
        if m['entity_ids']:lines += ['**Resolved people:** '+', '.join(f'[{e}](#{e})' for e in m['entity_ids']),'']
        if m['claim_revision']:
            lines += ['**Claim revision (excluded from active retrieval):** '+safe(dumps(m['claim_revision'])),'']
    other=[n for n in graph['nodes'] if n['type'] not in ('voice','semantic','episodic')]
    if other:
        lines += ['## Other original nodes','']
        for n in other:
            lines += [f'<a id="node-{n["id"]}"></a>',f"### {n['type']} {n['id']}",'',safe(dumps(n)),'']
    lines += ['## Original graph edges','',
              '| Source | Target | Weight |','| --- | --- | ---: |']
    for e in graph['edges']:
        lines.append(f"| [{e['source_type']}_{e['source']}](#node-{e['source']}) | [{e['target_type']}_{e['target']}](#node-{e['target']}) | {e['weight']} |")
    lines += ['','## Deferred cases','']
    deferred=[d for d in execution['accepted'] if d['op']=='defer']
    for d in deferred:
        lines += [f"### {d['decision_id']}",'', '**Targets:** '+safe(', '.join(d['target_ids'])),'',safe(d['reason']),'']
    if not deferred:lines+=['None.','']
    lines+=['## Rejected decisions','']
    for item in execution['rejected']:
        lines += ['- '+safe(item['decision'].get('decision_id','unknown'))+': '+safe(item['reason'])]
    if not execution['rejected']:lines+=['None.']
    return '\n'.join(lines)+'\n'
