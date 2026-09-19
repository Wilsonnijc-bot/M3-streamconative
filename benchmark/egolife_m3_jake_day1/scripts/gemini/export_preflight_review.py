"""Export the selected live preflight, not the full first-ten benchmark."""
import csv
import hashlib
import json
import shutil
from pathlib import Path

RUN=Path('/opt/streammeco/run/egolife_10q_gemini')
SRC=RUN/'smoke/results'
OUT=RUN/'preflight_review'
for name in ['constructed_memory','retrieved_memory','provenance']:(OUT/name).mkdir(parents=True,exist_ok=True)
NAMES={'A':'method_A_normal_streammeco.jsonl','B':'method_B_streammeco_oneshot.jsonl','C':'method_C_compressed_oneshot.jsonl','D':'method_D_mandol.jsonl'}
rows={m:json.loads((SRC/n).read_text()) for m,n in NAMES.items()}
audits=[json.loads(p.read_text()) for p in sorted((RUN/'results/clip_audits').glob('*_audit.json'))]
assert len(audits)==3 and set(rows)==set('ABCD')
comp=json.loads((SRC/'compression_metrics.json').read_text())[0]
adapt=json.loads((SRC/'mandol_adapted/q01/adapter_metrics.json').read_text())
metadata=json.loads((SRC/'memory/q01_uncompressed/metadata.json').read_text())
source_segments=metadata['source_segments']
q=rows['A']['question']

def write(path,text):path.write_text(text.rstrip()+'\n')
def copy(src,dest):dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dest)
def table(headers,values):
    lines=['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']
    for row in values:lines.append('| '+' | '.join(str(x).replace('|','\\|').replace('\n',' ') for x in row)+' |')
    return '\n'.join(lines)
def num(x):return f'{x:,.2f}'

# Exact native and compressed memory, plus the adaptor's own complete representation.
for label,source in [('uncompressed',SRC/'memory/q01_uncompressed'),('compressed',SRC/'streammeco_compressed/q01')]:
    for name in ['graph.pkl','graph.json','nodes.jsonl','edges.jsonl','metadata.json']:
        copy(source/name,OUT/'constructed_memory'/label/name)
shutil.copytree(SRC/'mandol_adapted/q01/graph',OUT/'constructed_memory/mandol',dirs_exist_ok=True)
copy(SRC/'mandol_adapted/q01/mapping_m3_to_mandol.json',OUT/'constructed_memory/mapping_m3_to_mandol.json')

lines=['# Constructed memory — three chronological clips','',
       'One fresh Gemini build: **18 episodic + 9 semantic + 3 voice nodes = 30 nodes**, with **7 edges**. No qualified face nodes were added. These are generated descriptions/inferences, not independently verified ground truth.','',
       'Coverage: **11:09:42.08–11:11:00.00** on Jake DAY1. The test question is timestamped **11:21:02.17**; the memory deliberately covers only the first three clips. It is not the complete Q1 benchmark snapshot.','']
for a,seg in zip(audits,source_segments):
    lines += [f'## Clip {a["clip_id"]} — {seg["source"]}', '',f'Source range: {seg["start_seconds_in_source"]:.2f}–{seg["end_seconds_in_source"]:.2f} seconds.', '', '### Episodic memory','']
    lines += ['- '+x for x in a['generated_memory']['video_description']]
    lines += ['', '### Semantic memory / model inferences','']
    lines += ['- '+x for x in a['generated_memory']['high_level_conclusions']]
    lines += ['']
graph=json.loads((SRC/'memory/q01_uncompressed/graph.json').read_text())
lines += ['## Node index','',table(['M3 ID','Type','Clip','Contents'],[[n['id'],n['type'],n['metadata'].get('timestamp','identity'),'<br>'.join(n['metadata'].get('contents',[]))] for n in graph['nodes']]),'',
          '## Saved representations','', '- [Uncompressed graph JSON](uncompressed/graph.json) · [exact Python pickle](uncompressed/graph.pkl)',
          '- [Compressed graph JSON](compressed/graph.json) · [exact Python pickle](compressed/graph.pkl)',
          '- [Mandol state](mandol/graph_state.json) · [M3→Mandol mapping](mapping_m3_to_mandol.json)',
          '', 'Compression retained 23 nodes (14 episodic, 6 semantic, 3 voice) and 5 edges. Mandol adapted the uncompressed 27 text memories and 3 identity entities; it imported no M3 vectors.']
write(OUT/'constructed_memory/README.md','\n'.join(lines))

for method,x in rows.items():
    copy(SRC/NAMES[method],OUT/'provenance'/NAMES[method])
    lines=[f'# Method {method} — retrieved memory','',f'**Question:** {q["question"]}', '',
           'Choices: '+'; '.join(f'{k}: {v}' for k,v in q['choices'].items()),'',
           f'**Answer:** {x["prediction"]} ({q["choices"].get(x["prediction"], "")}); dataset label: {x["gold_answer"]}. **Functional test passed**; this incomplete-memory trial is not a full benchmark accuracy measurement.','',
           f'Retrieval requests: **{x["retrieval_round_count"]}**. Gemini calls: **{len(x["controller_calls"]) if method=="A" else 1}**.','']
    if method=='A':
        lines+=['## Controller actions','',table(['Call','Action','Content','Gemini ms'],[[c['step'],c.get('action_type',c['purpose']),c.get('action_content',c.get('response','')),num(c['latency_ms'])] for c in x['controller_calls']]),'']
    for i,event in enumerate(x['retrieval_rounds'],1):
        lines += [f'## Retrieval {i}', '', '**Query:** '+event.get('query_text',str(x['retrieval_query'])), '',f'Total retrieval: **{num(event["retrieval"]["TOTAL_RETRIEVAL_MS"])} ms**.','']
        for evidence in event['evidence']:
            lines += [f'### Rank {evidence["rank"]} — node `{evidence["node_id"]}`','',f'Type: {evidence["node_type"]}; clip: {evidence.get("timestamp")}; score: {evidence.get("score")}.']
            if 'm3_node_id' in evidence:lines += [f'Mapped M3 node: `{evidence["m3_node_id"]}`. MemorySpaces: '+', '.join(f'`{v}`' for v in evidence.get('memory_spaces',[]))+'.']
            lines += ['']+['- '+v for v in evidence['contents']]+['']
    lines += ['## Raw final answer','','```text',x['raw_answer'],'```']
    write(OUT/'retrieved_memory'/f'{method}.md','\n'.join(lines))
    write(OUT/'retrieved_memory'/f'{method}.json',json.dumps(x['retrieval_rounds'],ensure_ascii=False,indent=2))

summary=[]
for m,x in rows.items():
    events=x['retrieval_rounds'];calls=x['controller_calls'] if m=='A' else [x['final_answer_call']]
    summary.append({'Method':m,'Memory nodes':x['memory']['nodes'],'Retrieval requests':len(events),'Gemini calls':len(calls),
                    'Embedding ms':sum(e.get('embedding_ms',e['embedding']['total_ms']) for e in events),
                    'Retrieval ms':sum(e['retrieval']['TOTAL_RETRIEVAL_MS'] for e in events),
                    'Gemini ms':sum(c['latency_ms'] for c in calls),'End-to-end ms':x['FULL_QUESTION_TO_ANSWER_MS'],
                    'Answer':x['prediction'],'Matches label':x['correct']})
with (OUT/'latency.csv').open('w') as f:
    writer=csv.DictWriter(f,fieldnames=list(summary[0]));writer.writeheader();writer.writerows(summary)
vlm=sum(a['latency_ms']['vlm_memory_generation'] for a in audits)
construction=sum(a['end_to_end_memory_generation_ms'] for a in audits)
lines=['# Gemini preflight — measured latency','',
       '**All four paths passed live construction/retrieval checks.** Three clips, one question, one selected trial per method. This is a functional preflight, **not** the 10-question benchmark; no meaningful P95 or accuracy estimate can be inferred from it.','',
       '## Question → answer','',table(['Method','Nodes','Retrieval requests','Gemini calls','Retrieval ms','Gemini ms','End-to-end ms','Answer'],[[x['Method'],x['Memory nodes'],x['Retrieval requests'],x['Gemini calls'],num(x['Retrieval ms']),num(x['Gemini ms']),num(x['End-to-end ms']),x['Answer']] for x in summary]),'',
       '**A:** normal controller. **B:** uncompressed one-shot. **C:** compressed one-shot. **D:** Mandol one-shot. A used four retrievals and six Gemini calls, including its forced final answer; B/C/D each used one retrieval request and one final-answer call.','',
       'Question: “Who used the screwdriver first?” Dataset label: **B — Alice**. A/B/C/D outputs: **D/B/A/'+rows['D']['prediction']+'**. Only '+', '.join(m for m,x in rows.items() if x['correct'])+' matched the label. The input covers 77.63 seconds of video, ending about 10 minutes before Q1; retrieved text does not establish who first used a screwdriver. A matching guess does not validate retrieval quality.','',
       '## Construction and offline preparation','',
       table(['Clip','Clip duration s','Total construction ms','Gemini ms','Text embedding ms','Nodes after'],[[a['clip_id'],f'{seg["end_seconds_in_source"]-seg["start_seconds_in_source"]:.2f}',num(a['end_to_end_memory_generation_ms']),num(a['latency_ms']['vlm_memory_generation']),num(a['latency_ms']['text_embedding']),a['counts']['nodes_after_clip']] for a,seg in zip(audits,source_segments)]),'',
       f'Three-clip construction: **{num(construction)} ms** summed clip processing; Gemini: **{num(vlm)} ms** across **3 memory calls**. These totals exclude Python startup and artifact-export overhead.','',
       table(['Offline stage','Wall ms','Details'],[['StreamMeCo compression',num(comp['compression_latency_ms']),f'30 → 23 nodes; {comp["memory_bytes_before"]:,} → {comp["memory_bytes_after"]:,} bytes; zero Gemini calls'],['M3 export',num(adapt['export_ms']),'Text/metadata export; native vectors omitted'],['Mandol index build',num(adapt['mandol_build_ms']),f'Includes {num(adapt["embedding"]["total_ms"])} ms across 2 embedding batches; zero reasoning calls']]),'',
       '## Retrieval stages','',
       table(['Method / round','Embedding ms','Dense search ms','StreamMeCo scoring ms','Graph selection ms','Retrieval wall ms'],[[f'{m}/{i}',num(e.get('embedding_ms',e['embedding']['total_ms'])),num(e.get('vector_search_ms',0)),num(e.get('streammeco_tmr_scoring_ms',0)),num(e.get('graph_node_selection_ms',0)),num(e['retrieval']['TOTAL_RETRIEVAL_MS'])] for m in 'ABC' for i,e in enumerate(rows[m]['retrieval_rounds'],1)]),'',
       'A/B/C use no sparse search or reranker. Query preparation and other small overheads remain in the exact per-round JSON. Controller query generation is included in the corresponding Gemini call, not counted a second time.','']
d=rows['D']['retrieval_rounds'][0];dr=d['retrieval'];features=dr.get('query_feature_metrics',{}).get('vectors',{})
lines += ['### Mandol internals','',table(['Stage','Measured ms','Interpretation'],[
    ['Query/MemorySpace selection',num(d['query_preparation_ms']),'Candidate scope selection'],
    ['Retriever initialization',num(dr.get('retriever_initialization_ms',0)),'Cold initialization inside this retrieval request'],
    ['Dense embedding',num(d['embedding']['total_ms']),'302.ai, 1024D'],
    ['Dense vector search',num(dr['dense_ms']),'Excludes remote embedding'],
    ['BM25 backend',num(next(x['latency_ms'] for x in dr['backend_calls'] if x['method']=='bm25')),'Includes lexical query processing; 0 hits is a valid no-match'],
    ['SPLADE backend',num(next(x['latency_ms'] for x in dr['backend_calls'] if x['method']=='splade')),'Includes local query encoding and sparse search'],
    ['RRF fusion',num(dr['fusion_ms']),'Fuses nonempty backend results'],
    ['MemoryUnit lookup',num(dr['memory_unit_lookup_ms']),'Nested within backend searches'],
    ['Candidate text/MemorySpace lookup',num(dr['candidate_space_lookup_ms']),'Prepares reranker inputs and provenance'],
    ['Cloud reranker',num(dr['rerank_ms']),'302.ai Qwen3 reranker'],
    ['Total retrieval',num(dr['TOTAL_RETRIEVAL_MS']),'Measured wall time; includes initialization']]),'',
    '**Do not add nested/parallel stages.** Dense, sparse and lookup timings overlap; total retrieval is measured independently. Offline compression/adaptation are excluded from question-to-answer latency. Non-streaming Gemini does not expose TTFT, so it is unavailable rather than zero.','',
    '## Separate embeddings and dependencies','',table(['Methods','Embeddings','Retrieval dependencies','Reasoning'],[
        ['A/B/C','OpenRouter openai/text-embedding-3-large, 3072D','Native M3 graph + StreamMeCo; separate StreamMeCo Python environment','302.ai gemini-3.8-flash'],
        ['D','302.ai Qwen/Qwen3-Embedding-0.6B, 1024D','Mandol environment; BM25 + original naver/splade-cocondenser-ensembledistil + Qwen/Qwen3-Reranker-0.6B','302.ai gemini-3.8-flash']]),'',
    'The SPLADE checkpoint is stored under the legacy local directory `naver/splade-v3`; the downloaded source is the original cocondenser checkpoint. Mandol re-embeds text and imports **no M3 vectors**. ASR, speaker and face preprocessing retain their existing models. No Qwen/Gemma/local reasoning model ran.','',
    '## Test evidence','',
    '- Three Gemini-built clips committed, including the formerly failing third clip; 30 nodes, 7 edges.',
    '- A/B/C/D retrieved nonempty evidence and returned a valid answer with the exact Gemini model ID.',
    '- 26 focused tests passed; the initially skipped cross-repository test was then run explicitly and passed.',
    '- Report/lineage validation test passed; it rejects changed snapshot hashes.',
    '- Mandol’s initial timing wrapper failed on its lazy dense loader. That bug was fixed; the detailed-timing retest passed. Prior failures remain in provenance.',
    '', '## Inspect the actual memory','',
    '- [Constructed memory and full node index](constructed_memory/README.md)',
    '- Retrieved evidence: [A, every controller round](retrieved_memory/A.md) · [B](retrieved_memory/B.md) · [C](retrieved_memory/C.md) · [D, mapped M3 IDs](retrieved_memory/D.md)',
    '- [Exact latency CSV](latency.csv) · [Raw test status](provenance/preflight_validation.json)']
write(OUT/'LATENCY.md','\n'.join(lines))
write(OUT/'README.md','# Gemini preflight review\n\n[Open the latency report](LATENCY.md) for measured construction and A/B/C/D timings.\n\n- [Constructed memory: all three clips and node IDs](constructed_memory/README.md)\n- Retrieved memory: [A](retrieved_memory/A.md) · [B](retrieved_memory/B.md) · [C](retrieved_memory/C.md) · [D](retrieved_memory/D.md)\n- [Raw latency CSV](latency.csv)\n\nThis folder contains the **three-clip functional preflight**, not completed results for the 40-trial benchmark. All methods used the same memory coverage; C compressed it and D re-embedded the exported text.')
for name in ['preflight.log','focused_tests.log','cross_repository_test.log','report_tests.log','retest_d.log']:
    copy(RUN/name,OUT/'provenance'/name)
for name in ['model_manifest.json','preflight_validation.json','compression_metrics.json','gemini_calls.jsonl']:
    copy(SRC/name,OUT/'provenance'/name)
copy(RUN/'results/gemini_calls.jsonl',OUT/'provenance/memory_gemini_calls.jsonl')
copy(RUN/'results/memory_construction_latency.jsonl',OUT/'provenance/memory_construction_latency.jsonl')
copy(SRC/'mandol_adapted/q01/adapter_metrics.json',OUT/'provenance/adapter_metrics.json')
copy(SRC/'mandol_adapted/q01/interchange/manifest.json',OUT/'provenance/mandol_export_manifest.json')
copy(RUN/'smoke/prior_attempts/method_D_initial_timing.jsonl',OUT/'provenance/method_D_initial_timing.jsonl')
write(OUT/'provenance/file_hashes.json',json.dumps({str(p.relative_to(OUT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.rglob('*') if p.is_file() and p.name!='file_hashes.json'},indent=2))
print('PREFLIGHT_REVIEW_EXPORTED',OUT,flush=True)
