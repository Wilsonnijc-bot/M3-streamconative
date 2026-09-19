"""Readable index for actual model-produced checkpoints, with evidence caveats."""
import argparse
from collections import Counter,defaultdict
from pathlib import Path
from .common import read,write


def cell(text):
    return str(text).replace('|','\\|').replace('\n','<br>')


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',default='consolidation/runs/live');args=p.parse_args()
    root=Path(args.root)
    index=['# Live MOSS + GPT-6 Astra consolidation','',
        '[Exact replay, MOSS transcript, Astra prompt/output, and updated graph](review/README.md)','',
        'Real MOSS-Transcribe-Diarize 0.9B inference on Hyperstack instance 1042997, followed by official GPT-6 Astra (high reasoning).',
        'Astra receives MOSS transcripts and timestamp/speaker alignments; it does not receive raw audio.',
        'All original voices and text remain preserved. These are model-supported interpretations, not verified identity ground truth.','',
        '| Checkpoint | People | Named | Assigned observations | Unresolved speech | Outputs |',
        '| --- | ---: | ---: | ---: | ---: | --- |']
    total_usage=Counter()
    for summary_file in sorted(root.glob('checkpoint_*.json')):
        summary=read(summary_file);minutes=summary['minutes']
        version=Path(summary['path'])
        state=read(version/'state.json');packet=read(version/'evidence.json');graph=read(version/'graph.json')
        execution=read(version/'execution.json');metadata=read(version/'llm_metadata.json')
        for key in ('input_tokens','output_tokens','total_tokens'):
            total_usage[key]+=metadata.get('usage',{}).get(key,0)
        case=root/f'{minutes}min';case.mkdir(exist_ok=True)
        observations=packet['observations']
        unresolved=sum(o['end_time']-o['start_time'] for o in observations if o['utterance_id'] not in state['assignments'])
        duration=defaultdict(float)
        for o in observations:
            if o['utterance_id'] in state['assignments']:
                duration[state['assignments'][o['utterance_id']]]+=o['end_time']-o['start_time']
        lines=[f'# Consolidation at {packet["current_cutoff"]:.2f} s','',
            f'Version: `{state["graph_version"]}`',
            f'Previous cutoff: {packet["previous_cutoff"]:.2f} s. Original observations: {len(observations)}.',
            f'Accepted decisions: {len(execution["accepted"])}; rejected decisions: {len(execution["rejected"])}.',
            '', '## Persistent people','',
            '| Entity | Supported name | Observations | Speech seconds | Source voices | Name evidence |',
            '| --- | --- | ---: | ---: | --- | --- |']
        for eid,entity in state['entities'].items():
            lines.append('| '+' | '.join(map(cell,[eid,entity['canonical_name'] or 'unnamed',len(entity['utterance_ids']),
                round(duration[eid],2),', '.join(entity['voice_ids']),', '.join(entity['name_evidence'])]))+' |')
        lines+=['','## Rejected decisions','']
        for item in execution['rejected']:
            lines.append(f"- `{item['decision'].get('decision_id')}` ({item['decision'].get('op')}): {item['reason']}")
        if not execution['rejected']:lines.append('None.')
        lines+=['','## Deferred decisions','']
        for d in execution['accepted']:
            if d['op']=='defer':lines.append('- '+', '.join(d['target_ids'])+': '+d['reason'])
        lines+=['','## Audio evidence','',
            f"MOSS segments: {summary['moss_segments']}; anonymous speakers: {summary['moss_speakers']}.",
            f"Candidate mixed voice clusters: {len(packet['candidate_mixed_clusters'])}.",
            f"Alignment statuses: {dict(Counter(a['alignment_status'] for a in packet['moss_alignments']))}.",
            '', '## Interpretation limits','',
            'Original CAM++ candidate scores were not recorded in the supplied caches; none were reconstructed or invented.',
            'MOSS speaker labels and M3 semantic claims may be wrong. No independent identity labels or QA evaluation were used.',
            'Unresolved speech duration sums observation durations, including overlap; it is not unique wall-clock coverage.',
            '', '## Exact provenance','']
        import os
        for label,name in [('Audit','audit.md'),('Graph','graph.json'),('Evidence','evidence.json'),('Original model request','llm_input.json'),
                           ('Raw model response','llm_response.json'),('Patch','patch.json'),('Historical/consolidated observations','views.json')]:
            lines.append(f'- [{label}]({os.path.relpath(version/name,case)})')
        (case/'summary.md').write_text('\n'.join(lines)+'\n')
        memory_lines=[f'# Canonical memory at {minutes} minutes','',
            'Only explicitly resolved/provenance-bound references change. Raw text is retained alongside each changed memory.','']
        changed=0
        for m in graph['canonical_memories']:
            if m['canonical_text']!=m['raw_text'] or m['claim_revision']:
                changed+=1
                memory_lines += [f"## {m['kind']} {m['memory_node_id']}",'',
                    '**Original:** '+m['raw_text'],'','**Canonical:** '+m['canonical_text'],'']
                if m['claim_revision']:memory_lines+=['**Claim revision:** '+str(m['claim_revision']),'']
        (case/'memories.md').write_text('\n'.join(memory_lines)+'\n')
        index.append(f"| {minutes} min ({packet['current_cutoff']} s) | {len(state['entities'])} | {len(summary['names'])} | {len(state['assignments'])}/{len(observations)} | {unresolved:.2f} s | [Summary]({minutes}min/summary.md) · [Changed memories]({minutes}min/memories.md) |")
        summary.update(unresolved_speech_s=unresolved,changed_memories=changed,
            alignment_statuses=dict(Counter(a['alignment_status'] for a in packet['moss_alignments'])))
        write(summary_file,summary)
    index+=['','The 40-minute run continues the 20-minute registry. Dense and lexical retrieval are rebuilt and published with each graph.',
        '',f"Official Astra token usage across completed checkpoints: {dict(total_usage)}.",
        '', 'Exact model artifacts are in the linked version directories; MOSS raw outputs and normalized segments are under `moss/`.',
        'Full prefix WAVs remain on the GPU at `/opt/streammeco/run/consolidation_live/results/` with SHA-256 provenance.','']
    (root/'README.md').write_text('\n'.join(index))
    print('\n'.join(index))


if __name__=='__main__':main()
