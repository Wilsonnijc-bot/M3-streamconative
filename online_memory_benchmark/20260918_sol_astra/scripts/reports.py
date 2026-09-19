"""Hourly inspectable graph replay and latency/retrieval reports from raw records."""
from collections import Counter
import json
import math
import pickle
import statistics
from bench_common import rows, read
from accuracy import summarize


def stats(values):
    values=sorted(v for v in values if isinstance(v,(int,float)) and math.isfinite(v))
    if not values:return '0 | — | — | —'
    return f'{len(values)} | {statistics.mean(values):.2f} | {statistics.median(values):.2f} | {values[max(0,math.ceil(.95*len(values))-1)]:.2f}'

def table(records,fields):
    text='Stage | N | Mean ms | Median ms | P95 ms\n--- | ---: | ---: | ---: | ---:\n'
    for label,getter in fields:
        text+=label+' | '+stats([getter(r) for r in records])+'\n'
    return text

def write_hour(graph,event,directory,folder,dataset,method,compression):
    cutoff=event['end_s'];counts=Counter(n.type for n in graph.nodes.values())
    text=f'# {dataset} / {method} / {cutoff:g} media seconds\n\n'
    text+='Graph: '+json.dumps(dict(counts,total=len(graph.nodes),edges=len(graph.edges),characters=len(graph.character_mappings)))+'\n\n'
    text+='## StreamMeCo\n\n```json\n'+json.dumps(compression,indent=2)+'\n```\n\n'
    previous=directory/f'hour_{int(cutoff//3600)-1:02d}/state.json'
    if previous.exists():
        old=pickle.loads((previous.parent/'graph.pkl').read_bytes())
        changes=dict(added_node_ids=sorted(set(graph.nodes)-set(old.nodes)),removed_node_ids=sorted(set(old.nodes)-set(graph.nodes)),
            previous_counts=dict(Counter(n.type for n in old.nodes.values())),character_mappings_changed=old.character_mappings!=graph.character_mappings)
        text+='## Changes since previous hour\n\n```json\n'+json.dumps(changes,indent=2)+'\n```\n\n'
    text+='## Character mappings\n\n```json\n'+json.dumps(graph.character_mappings,ensure_ascii=False,indent=2)+'\n```\n\n'
    text+='## Chronological memory replay\n\n'
    for clip,ids in sorted(graph.text_nodes_by_clip.items()):
        start,end=graph.segment_times[clip];text+=f'### Clip {clip} / {start:g}–{end:g}s\n\n'
        for node_id in ids:
            if node_id not in graph.nodes:continue
            node=graph.nodes[node_id]
            related=[f'{graph.nodes[b].type}_{b}' for a,b in graph.edges if a==node_id and b in graph.nodes and graph.nodes[b].type in ('voice','img')]
            canonical=node.metadata.get('retrieval_contents',node.metadata['contents'])
            text+=f'- {node.type}_{node_id}: '+ ' / '.join(canonical)+'\n'
            text+='  Source: '+ ' / '.join(node.metadata['contents'])+'; related: '+', '.join(related)+'\n'
        text+='\n'
    if method in ('C3','C4') and cutoff==3600:
        text+='## First-hour consolidation\n\n'+''.join(f'- [{t//60:02d} minutes](../consolidation/event_{t:04d}.md)\n' for t in (1200,2400,3600))+'\n'
    (folder/'memory.md').write_text(text)
    construction=[r for r in rows(directory/'construction.jsonl') if cutoff-3600<r['benchmark_timestamp']<=cutoff]
    qa=[]
    for p in directory.glob('snapshots/*/answers/*/*/result.json'):
        r=read(p)
        if r['benchmark_timestamp']<=cutoff:qa.append(r)
    latency='# Latency\n\nNested stages overlap; values are measured independently. Missing values remain missing.\n\n## Construction (current hour)\n\n'
    fields=sorted({k for r in construction for k in r.get('latency_ms',{})})
    latency+=table(construction,[(k,lambda r,k=k:r.get('latency_ms',{}).get(k)) for k in fields])
    builds=[]
    for snapshot in directory.glob('snapshots/*/snapshot.json'):
        stamp=read(snapshot)['media_timestamp']
        if not cutoff-3600<stamp<=cutoff:continue
        loc=snapshot.parent
        if (loc/'mandol_build.json').exists():
            record=read(loc/'mandol_build.json')
            record['export_ms']=read(loc/'mandol_request.json')['export_ms']
            record['warmup_ms']=read(loc/'mandol_initialization.json')['index_reload_and_warmup_ms'] if (loc/'mandol_initialization.json').exists() else None
            builds.append(record)
    latency+='\n## Mandol adapter/index construction (one sample per snapshot; excluded from warm retrieval)\n\n'
    latency+=table(builds,[('M3 export',lambda r:r['export_ms']),('Adapter and index build total',lambda r:r['build_ms']),
        ('Dense embedding (nested in build)',lambda r:r.get('dense_embedding_ms')),('Index reload / warmup',lambda r:r['warmup_ms'])])
    latency+='\nBuild totals include nested encoding/index stages; they are not added to question retrieval latency.\n'
    for path in ('R1','R2'):
        subset=[r for r in qa if r['retrieval_method']==path and cutoff-3600<r['benchmark_timestamp']<=cutoff]
        latency+=f'\n## {path} retrieval and answer (current hour)\n\n'
        latency+=table(subset,[('retrieval',lambda r:r['retrieval']['retrieval_ms']),('TTFT',lambda r:r['answer']['ttft_ms']),
            ('full response',lambda r:r['answer']['generation_complete_ms']),('after first token',lambda r:r['answer']['after_first_token_ms']),
            ('question to first token',lambda r:r['question_to_first_token_ms']),('question to completion',lambda r:r['question_to_complete_answer_ms'])])
    if (directory/'consolidation.jsonl').exists():
        latency+='\n## Consolidation (current hour)\n\n'
        for r in rows(directory/'consolidation.jsonl'):
            if cutoff-3600<r['media_timestamp']<=cutoff:latency+='```json\n'+json.dumps({k:v for k,v in r.items() if k not in ('before_mappings','after_mappings')},indent=2)+'\n```\n\n'
    (folder/'latency.md').write_text(latency)
    retrieval='# Retrieval through this hour\n\nConstruction | Retrieval | Correct/N | Retrieval median ms | TTFT median ms | End-to-end median ms\n--- | --- | --- | ---: | ---: | ---:\n'
    for path in ('R1','R2'):
        sub=[r for r in qa if r['retrieval_method']==path]
        score=summarize(sub)
        med=lambda xs: f'{statistics.median(xs):.2f}' if xs else '—'
        retrieval+=f"{method} | {path} | {score['correct']}/{score['total']} | {med([r['retrieval']['retrieval_ms'] for r in sub])} | {med([r['answer']['ttft_ms'] for r in sub])} | {med([r['question_to_complete_answer_ms'] for r in sub])}\n"
    for r in sorted(qa,key=lambda r:(r['benchmark_timestamp'],r['question']['question_id'],r['retrieval_method'])):
        retrieval+=f"\n## {r['question']['question_id']} / {r['retrieval_method']} / {r['benchmark_timestamp']:g}s\n\n"
        retrieval+='```json\n'+json.dumps(r,ensure_ascii=False,indent=2)+'\n```\n'
    (folder/'retrieval.md').write_text(retrieval)
