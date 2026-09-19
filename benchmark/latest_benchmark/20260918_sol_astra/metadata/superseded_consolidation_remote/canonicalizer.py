"""Canonical text requires an explicit scoped reference or observation provenance."""
import re


def canonicalize(memories, observations, state):
    lookup={o['utterance_id']:o for o in observations}
    output=[]
    for memory in memories:
        m=dict(memory)
        text=m['raw_text']
        replacements=[]
        for ref in state['references'].values():
            if ref['memory_node_id']==m['memory_node_id']:
                for match in re.finditer(re.escape(ref['mention']),text):
                    replacements.append((match.start(),match.end(),ref['entity_id']))
        # No clip-wide/global substitution: only explicit observation IDs bound to a memory.
        for voice in set(re.findall(r'<(voice_\d+)>',text)):
            uids=[u for u in m.get('utterance_ids',[]) if u in lookup and lookup[u]['original_voice_id']==voice]
            entities={state['assignments'].get(u) for u in uids}
            if uids and len(entities)==1 and None not in entities:
                for match in re.finditer(re.escape('<'+voice+'>'),text):
                    replacements.append((match.start(),match.end(),next(iter(entities))))
        replacements=sorted(set(replacements))
        # Conflicting/overlapping mention spans are kept raw, never order-dependent.
        usable=[r for r in replacements if not any(r!=q and r[0]<q[1] and q[0]<r[1] for q in replacements)]
        for start,end,eid in reversed(usable):
            entity=state['entities'][eid]
            text=text[:start]+(entity['canonical_name'] or '<'+eid+'>')+text[end:]
        m['canonical_text']=text
        m['entity_ids']=sorted({r[2] for r in usable})
        m['claim_revision']=state['claims'].get(m['memory_node_id'])
        m['retrieval_active']=not bool(m['claim_revision'])
        output.append(m)
    return output
