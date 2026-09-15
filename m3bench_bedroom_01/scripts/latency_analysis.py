import json,statistics

def rows(p):
 if not p.exists():return []
 return [json.loads(s) for s in p.read_text().splitlines() if s.strip()]
def build_analysis(root):
 out=['## Timing overview','','Warm retrieval includes the actual query embedding and all search/rerank work. Index/model loading and the unrelated warmup probe are excluded. Separate semantic grading is excluded from QA timing. Concurrent stages and nested measurements are not additive.','']
 policy_path=root.parent/'parallel_eval/policy.json'
 if policy_path.exists():
  policy=json.loads(policy_path.read_text())
  out+=['### Parallel execution context','',
        'A/B/C/D retain separate per-question and per-round timers. Method locks and process startup occur before snapshot loading/warmup and outside timed QA. Adaptation, warmup, grading and log merging are excluded. Concurrent method durations must not be summed as elapsed benchmark time. Shared GPU/API contention can affect measured latency.', '',
        'The handover preserved completed answers. Rows not completed at handover are labeled “handover / parallel period”; an already-running question may straddle the boundary. This classification does not claim isolated hardware before the change.', '',
        '| Method | Period | Answers | Mean retrieval per round ms | Mean full QA ms |',
        '| --- | --- | ---: | ---: | ---: |']
  for method,name in [('A','method_A_normal_streammeco.jsonl'),('B','method_B_streammeco_oneshot.jsonl'),('C','method_C_compressed_oneshot.jsonl'),('D','method_D_mandol.jsonl')]:
   records=rows(root/name);before=set(policy['completed_before_parallel'].get(method,[]))
   groups=([('Later D100/20 rerun',records)] if method=='D' and (root/'method_D_selection.json').exists() else [('Before handover',[r for r in records if r['question_index'] in before]),('Handover / parallel period',[r for r in records if r['question_index'] not in before])])
   for label,group in groups:
    if not group:continue
    retrieval=[t['retrieval']['TOTAL_RETRIEVAL_MS'] for q in group for t in q['retrieval_rounds']]
    full=[q['FULL_QUESTION_TO_ANSWER_MS'] for q in group]
    out.append(f'| {method} | {label} | {len(group)} | {statistics.mean(retrieval):,.2f} | {statistics.mean(full):,.2f} |')
  out+=['', 'Method-wide statistics below combine these labeled periods; use the split above when comparing scheduling conditions. Exact call timings are retained in the raw per-method rows and telemetry.', '']
 audits=rows(root/'memory_construction_latency.jsonl')
 if audits:
  out+=['### Memory construction: mean and median','','| Stage | N | Mean ms | Median ms |','| --- | ---: | ---: | ---: |']
  for key,label in [('clip_decode','Decode'),('deepgram_asr','Deepgram'),('mai_transcribe_asr','MAI'),('asr_total','Concurrent ASR wall time'),('speech_embedding_campplus','CAM++ speaker embedding'),('facial_detection_recognition_buffalo_l','Face detection/recognition'),('face_clustering','Face clustering'),('vlm_context_preparation','VLM context preparation'),('vlm_memory_generation','Gemini memory generation'),('text_embedding','Whole-clip text embedding batch'),('graph_update_total','Graph update')]:
   values=[v for a in audits if isinstance(v := (a.get('stage_details',{}).get('vlm',{}).get('context_preparation_ms') if key=='vlm_context_preparation' else a.get('latency_ms',{}).get(key)),(int,float))]
   if values:out.append(f'| {label} | {len(values)} | {statistics.mean(values):,.2f} | {statistics.median(values):,.2f} |')
  out+=['','Missing stage values are omitted rather than treated as zero; provider retries remain in measured totals. Per-text latency within a batch is unavailable.','']
 for method,name in [('A','method_A_normal_streammeco.jsonl'),('B','method_B_streammeco_oneshot.jsonl'),('C','method_C_compressed_oneshot.jsonl'),('D','method_D_mandol.jsonl')]:
  records=rows(root/name)
  if not records:continue
  rounds=[r for q in records for r in q['retrieval_rounds']]
  out += [f'### Method {method}: warm retrieval per round','','| Stage | N | Mean ms | Median ms |','| --- | ---: | ---: | ---: |']
  getters=[('Query text embedding',lambda r:r.get('embedding_ms',r.get('embedding',{}).get('total_ms'))),('Dense vector search',lambda r:r['retrieval'].get('dense_ms')),('Sparse backends (overlap with dense)',lambda r:r['retrieval'].get('sparse_ms')),('StreamMeCo scoring',lambda r:r.get('streammeco_tmr_scoring_ms')),('Fusion',lambda r:r['retrieval'].get('fusion_ms')),('Node/unit lookup (nested)',lambda r:r['retrieval'].get('memory_unit_lookup_ms',r.get('graph_node_selection_ms'))),('Reranker',lambda r:r['retrieval'].get('rerank_ms')),('Total retrieval wall time',lambda r:r['retrieval']['TOTAL_RETRIEVAL_MS'])]
  for label,get in getters:
   values=[v for r in rounds if isinstance(v:=get(r),(int,float))]
   if values:out.append(f'| {label} | {len(values)} | {statistics.mean(values):,.2f} | {statistics.median(values):,.2f} |')
  out+=['']
  if method=='A':out+=['A can perform multiple retrieval rounds per question; these are per-round statistics. Full QA totals appear below.','']
 out+=['## Question-level stages: mean and median','',
       'Each row below has one observation per answered question. A’s Gemini total includes its final answer; the final-answer row is a subset, not an additional cost.', '']
 for method,name in [('A','method_A_normal_streammeco.jsonl'),('B','method_B_streammeco_oneshot.jsonl'),('C','method_C_compressed_oneshot.jsonl'),('D','method_D_mandol.jsonl')]:
  records=rows(root/name)
  if not records:continue
  stages=[('Retrieval across all rounds',lambda q:sum(t['retrieval']['TOTAL_RETRIEVAL_MS'] for t in q['retrieval_rounds'])),
          ('All Gemini reasoning / answer calls',lambda q:sum(c['latency_ms'] for c in q['controller_calls']) if q.get('controller_calls') else q['final_answer_model_ms']),
          ('Final answer call (included above)',lambda q:q['final_answer_model_ms']),
          ('Full question → answer',lambda q:q['FULL_QUESTION_TO_ANSWER_MS']),
          ('Snapshot loading — excluded',lambda q:q.get('snapshot_load_ms_excluded')),
          ('Neutral warmup — excluded',lambda q:q.get('warmup_ms_excluded'))]
  out += [f'### Method {method}: per-question timings','','| Stage | N | Mean ms | Median ms |','| --- | ---: | ---: | ---: |']
  for label,get in stages:
   values=[v for q in records if isinstance(v:=get(q),(int,float))]
   if values:out.append(f'| {label} | {len(values)} | {statistics.mean(values):,.2f} | {statistics.median(values):,.2f} |')
  out+=['']
 out+=['## Offline preparation: mean and median','',
       'These are original preparation costs, outside timed QA. The D100/20 rerun reused those indexes. N counts saved per-question preparation records, including repeated query cutoffs.', '',
       '| Stage | N | Mean ms | Median ms |','| --- | ---: | ---: | ---: |']
 compress=json.loads((root/'compression_metrics.json').read_text()) if (root/'compression_metrics.json').exists() else []
 adapters=[json.loads(p.read_text()) for p in sorted((root/'mandol_adapted').glob('q*/adapter_metrics.json'))]
 for label,values in [('Compression',[x['compression_latency_ms'] for x in compress]),('Mandol export',[x['export_ms'] for x in adapters]),('Mandol build / embedding / sparse index',[x['mandol_build_ms'] for x in adapters])]:
  if values:out.append(f'| {label} | {len(values)} | {statistics.mean(values):,.2f} | {statistics.median(values):,.2f} |')
 out+=['']
 return out
