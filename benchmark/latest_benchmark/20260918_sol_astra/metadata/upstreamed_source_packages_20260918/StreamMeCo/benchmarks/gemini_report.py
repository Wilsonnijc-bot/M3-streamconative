"""Finalize and validate the OpenAI first-ten benchmark's auditable artifacts."""
import csv
import hashlib
import json
from pathlib import Path
from statistics import mean, median

NAMES = {'A':'method_A_normal_streammeco.jsonl','B':'method_B_streammeco_oneshot.jsonl',
         'C':'method_C_compressed_oneshot.jsonl','D':'method_D_mandol.jsonl'}

def read(path):
    return [json.loads(x) for x in path.read_text().splitlines() if x.strip()]

def write(value,path):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')

def report(args):
    root=args.results
    rows=[]
    all_events=[]
    for method,name in NAMES.items():
        for x in read(root/name):
            rounds=x['retrieval_rounds']
            def stage(key):
                return sum(e['retrieval'].get(key,0) for e in rounds)
            calls=x['controller_calls'] if method=='A' else [x['final_answer_call']]
            metadata=json.loads((root/'memory'/f"q{x['question_index']:02d}_uncompressed"/'metadata.json').read_text())
            row={'Latency mode':x.get('latency_mode','unspecified'),'Skipped segments':len(metadata.get('skipped_segments',[])),'ASR degraded segments':len(metadata.get('asr_degraded_segments',[])),'Q':x['question_index'],'Method':method,'Memory nodes':x['memory']['nodes'],
                 'Retrieval queries':x['retrieval_round_count'],'OpenAI calls':len(calls),
                 'Embed ms':sum(e.get('embedding_ms',e['embedding']['total_ms']) for e in rounds),
                 'Dense ms':stage('dense_ms'),'Sparse ms':stage('sparse_ms'),
                 'StreamMeCo/Mandol ms':stage('StreamMeCo/TMR_ms')+stage('fusion_ms'),
                 'Graph lookup ms':stage('memory_unit_lookup_ms')+stage('graph_traversal_ms'),
                 'Rerank ms':stage('rerank_ms'),'Retrieval total ms':stage('TOTAL_RETRIEVAL_MS'),
                 'OpenAI answer/controller ms':sum(c['latency_ms'] for c in calls),
                 'End-to-end ms':x['FULL_QUESTION_TO_ANSWER_MS'],'Answer':x['prediction'],'Correct':x['correct']}
            rows.append(row)
            for i,event in enumerate(rounds,1):
                all_events.append({**event, 'question_id':x['question']['id'], 'question_index':x['question_index'], 'method':method, 'round':event.get('round',i)})
    rows.sort(key=lambda x:(x['Q'],x['Method']))
    with (root/'comparison.csv').open('w') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    with (root/'detailed_retrieval_events.jsonl').open('w') as f:
        for event in all_events: f.write(json.dumps(event,ensure_ascii=False)+'\n')
    aggregates={}
    for m in NAMES:
        selected=[x for x in rows if x['Method']==m]
        r=[x['Retrieval total ms'] for x in selected]
        e=[x['End-to-end ms'] for x in selected]
        aggregates[m]={'correct':sum(x['Correct'] for x in selected),'questions':len(selected),
                       'mean_retrieval_ms':mean(r),'median_retrieval_ms':median(r),'p95_retrieval_ms':sorted(r)[-1],
                       'mean_end_to_end_ms':mean(e),'median_end_to_end_ms':median(e),
                       'mean_embedding_ms':mean(x['Embed ms'] for x in selected),
                       'mean_openai_ms_per_question':mean(x['OpenAI answer/controller ms'] for x in selected),
                       'mean_openai_ms_per_call':sum(x['OpenAI answer/controller ms'] for x in selected)/sum(x['OpenAI calls'] for x in selected),
                       'mean_openai_calls':mean(x['OpenAI calls'] for x in selected),
                       'mean_retrieval_queries':mean(x['Retrieval queries'] for x in selected)}
    write(aggregates,root/'aggregate_metrics.json')
    cols=list(rows[0]);lines=['# Jake DAY1 - OpenAI first ten questions','',
        'Reasoning: GPT-5.6 Sol via OpenAI with medium reasoning. A/B/C use OpenRouter text-embedding-3-large; D independently embeds exported text with 302.ai Qwen3-Embedding-0.6B (1024D), local SPLADE and BM25, then OpenRouter Qwen3-Reranker-0.6B.',
        '', 'All QA rows measure warm local retrieval with an uncached question. Snapshot loading, offline adaptation/compression, and fixed neutral-probe warmup are excluded and recorded in retrieval_warmup.jsonl. Actual query embeddings, searches and reranking remain timed; cloud-provider internal model state is not controlled. Mandol backend times include nested embeddings and unit lookup; parallel/nested timings are not additive. Retrieval total is measured wall time. TTFT is unavailable for the non-streaming API. Compression and adaptor use zero reasoning calls.', '',
        '| '+' | '.join(cols)+' |','| '+' | '.join(['---']*len(cols))+' |']
    for r in rows:lines.append('| '+' | '.join(f'{r[c]:.2f}' if isinstance(r[c],float) else str(r[c]) for c in cols)+' |')
    lines+=['','## Per-method aggregates','','```json',json.dumps(aggregates,indent=2),'```']
    (root/'comparison.md').write_text('\n'.join(lines)+'\n')
    mapping={}
    provenance=[]
    for i in range(1,11):
        p=root/'memory'/f'q{i:02d}_uncompressed'/'graph.pkl'
        md=json.loads(p.with_name('metadata.json').read_text())
        provenance.append({'question_index':i,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'latest_segment_end':max(x['absolute_end_seconds'] for x in md['source_segments']), 'question_time':md['query_time_seconds']})
        mapping[f'q{i:02d}']=json.loads((root/'mandol_adapted'/f'q{i:02d}'/'mapping_m3_to_mandol.json').read_text())
    write(mapping,root/'mandol'/'mapping_m3_to_mandol.json')
    write(provenance,root/'snapshot_provenance.json')

def validate(args):
    root=args.results
    problems=[]
    count=0
    for method,name in NAMES.items():
        data=read(root/name);count+=len(data)
        if sorted(x['question_index'] for x in data)!=list(range(1,11)):problems.append(f'{method}: wrong question set')
        for x in data:
            if x.get('latency_mode')!='warm_retrieval_uncached_question':problems.append('non-warm trial')
            if x['prediction'] not in ['A','B','C','D']:problems.append(f'{method}: invalid prediction')
            i=x['question_index']
            native=root/'memory'/f'q{i:02d}_uncompressed'/'graph.pkl'
            native_hash=hashlib.sha256(native.read_bytes()).hexdigest()
            if method in ('A','B') and x.get('evaluated_graph_sha256')!=native_hash:problems.append('snapshot lineage mismatch')
            if method=='C':
                compressed=root/'streammeco_compressed'/f'q{i:02d}'/'graph.pkl'
                meta=json.loads(compressed.with_name('metadata.json').read_text())
                if meta['source_graph_sha256']!=native_hash:problems.append('compression lineage mismatch')
                if x.get('evaluated_graph_sha256')!=hashlib.sha256(compressed.read_bytes()).hexdigest():problems.append('compressed evaluation mismatch')
            if method=='D':
                manifest=json.loads((root/'mandol_adapted'/f'q{i:02d}'/'interchange'/'manifest.json').read_text())
                if manifest['source_graph_sha256']!=native_hash:problems.append('Mandol lineage mismatch')
            calls=x['controller_calls'] if method=='A' else [x['final_answer_call']]
            if any(c['model']!='gpt-5.6-sol' or c['returned_model']!='gpt-5.6-sol' for c in calls):problems.append('non-OpenAI reasoning')
            if method!='A' and (x['retrieval_round_count']!=1 or x['controller_calls']):problems.append('one-shot violation')
            if len(x['retrieval_rounds'])!=x['retrieval_round_count']:problems.append('retrieval count mismatch')
            if method=='D':
                if not x['retrieval_rounds'][0]['retrieval'].get('warm_engine'):problems.append('Mandol engine not warm')
                kinds={b['method'] for b in x['retrieval_rounds'][0]['retrieval']['backend_calls']}
                if kinds!={'bm25','cosine_similarity','splade'}:problems.append('missing Mandol backend')
    for x in json.loads((root/'snapshot_provenance.json').read_text()):
        if x['latest_segment_end']>x['question_time']+1e-6:problems.append('future leakage')
    calls=read(root/'gemini_calls.jsonl')
    if any(x['model']!='gpt-5.6-sol' for x in calls):problems.append('non-OpenAI request')
    for name in ['memory_construction_latency.jsonl','compression_metrics.json','comparison.csv','comparison.md','detailed_retrieval_events.jsonl']:
        if not (root/name).stat().st_size:problems.append('empty '+name)
    result={'status':'complete' if count==40 and not problems else 'failed','qa_rows':count,'problems':problems}
    write(result,root/'validation.json')
    if result['status']!='complete':raise RuntimeError(result)
    print('BENCHMARK_VALIDATION_COMPLETE qa_rows=40',flush=True)
