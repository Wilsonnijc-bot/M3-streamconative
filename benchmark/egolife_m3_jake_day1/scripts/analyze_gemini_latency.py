"""Source-derived interpretation of the completed Gemini latency measurements."""
import json
from pathlib import Path
from statistics import mean,median

def read_jsonl(path):return [json.loads(x) for x in path.read_text().splitlines() if x.strip()]
def get(obj,path):
    for key in path.split('.'):
        if not isinstance(obj,dict):return None
        obj=obj.get(key)
    return obj

def stats(items,selector):
    values=[selector(x) for x in items]
    values=[float(v) for v in values if isinstance(v,(int,float)) and not isinstance(v,bool)]
    return {'n':len(values),'mean':mean(values) if values else None,'median':median(values) if values else None}
def f(x):
    if x is None:return '—'
    if 0 < abs(x) < 0.0001:return f'{x:.6f}'
    return f'{x:,.2f}' if abs(x)>=1 or x==0 else f'{x:.4f}'
def table(headers,rows):
    return '\n'.join(['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']+['| '+' | '.join(str(v) for v in row)+' |' for row in rows])

def build_analysis(root):
    root=Path(root);data={}
    for m in 'ABCD':
        paths=list(root.glob('method_'+m+'_*.jsonl'))
        if len(paths)!=1:return []
        data[m]=read_jsonl(paths[0])
        if len(data[m])!=10:return []
    rounds={m:[e for x in xs for e in x['retrieval_rounds']] for m,xs in data.items()}
    def total(x):return sum(e['retrieval']['TOTAL_RETRIEVAL_MS'] for e in x['retrieval_rounds'])
    def qstat(m,fn):return stats(data[m],fn)
    def rstat(m,path):return stats(rounds[m],lambda x:get(x,path))
    b=rstat('B','retrieval.TOTAL_RETRIEVAL_MS');c=rstat('C','retrieval.TOTAL_RETRIEVAL_MS');d=rstat('D','retrieval.TOTAL_RETRIEVAL_MS')
    de=rstat('D','embedding.total_ms');dr=rstat('D','retrieval.rerank_ms')
    bd=rstat('B','vector_search_ms');cd=rstat('C','vector_search_ms')
    be=rstat('B','embedding_ms');ce=rstat('C','embedding_ms')
    audits=sorted([json.loads(p.read_text()) for p in (root/'clip_audits').glob('*_audit.json')],key=lambda x:x['clip_id'])
    opt=[x for x in audits if x['clip_id']>=27];early=[x for x in audits if x['clip_id']<27]
    schedule=read_jsonl(root/'segment_schedule_events.jsonl')
    vlm=stats(opt,lambda x:x['latency_ms'].get('vlm_memory_generation'))
    ordered=stats(opt,lambda x:x.get('ordered_processing_ms'))
    forced=sum(any(c.get('purpose')=='forced_final_answer' for c in x['controller_calls']) for x in data['A'])
    b_slow=max(data['B'],key=lambda x:x['FULL_QUESTION_TO_ANSWER_MS'])
    d_slow=max(data['D'],key=lambda x:x['retrieval_rounds'][0]['retrieval']['rerank_ms'])
    slow_vlm=max(opt,key=lambda x:x['latency_ms']['vlm_memory_generation'])
    lines=['## Analysis — where the time goes','',
        '**The main costs are model/API calls, not graph bookkeeping.** Mandol’s two cloud stages dominate its warm retrieval; StreamMeCo’s one-shot retrieval is mostly embedding plus local similarity search; Gemini generation dominates memory construction.','',
        'This analysis uses the **10 completed questions per method** and **144 committed segments**. Retrieval values below are milliseconds; the overview explicitly uses seconds. `N` is the number of available, non-null stage observations. Missing measurements are not replaced by zero.','',
        '**Measurement boundary:** all QA engines were warmed with an unrelated probe; the actual question and its embeddings were uncached. Offline adaptation, snapshot loading and warmup are excluded. The original evaluation shared GPU resources with Qwen. Selected D rerun measurements, when present, come from a later execution period. These are potentially contended observations, not isolated-load measurements.','',
        '### 1. Overall picture','']
    overview=[]
    for m,label in [('A','A · controller'),('B','B · one-shot'),('C','C · compressed one-shot'),('D','D · Mandol one-shot')]:
        rs=qstat(m,total);qs=qstat(m,lambda x:x['FULL_QUESTION_TO_ANSWER_MS'])
        overview.append([label,f"{sum(x['correct'] for x in data[m])}/10",f(mean(x['retrieval_round_count'] for x in data[m])),f(mean(len(x['controller_calls']) if m=='A' else 1 for x in data[m])),f(rs['mean']/1000),f(rs['median']/1000),f(qs['mean']/1000),f(qs['median']/1000)])
    lines += [table(['Method','Correct','Retrievals / Q','Gemini calls / Q','Mean retrieval s','Median retrieval s','Mean total QA s','Median total QA s'],overview),'',
        f'- **Mandol vs B:** mean warm retrieval is {d["mean"]/b["mean"]:.2f}× longer. This is predominantly the extra reranker call and the different embedding service, not slow local vector search.',
        f'- **Compression:** C saves {b["mean"]-c["mean"]:.2f} ms in mean retrieval versus B ({100*(1-c["mean"]/b["mean"]):.1f}%). Its mean local vector-search time is {100*(1-cd["mean"]/bd["mean"]):.1f}% lower. The embedding medians are almost identical, so do not credit compression for differences in cloud embedding response time.',
        f'- **Controller:** A used four retrieval rounds and six Gemini calls on every question in this run, reaching the forced-final-answer cap on **{forced}/10 questions**. It obtained the same 4/10 accuracy as B while taking much longer. This is evidence about these ten questions, not a general accuracy ranking.',
        f'- **Total QA is not retrieval latency:** B’s Q{b_slow["question_index"]} took {b_slow["FULL_QUESTION_TO_ANSWER_MS"]/1000:.2f} seconds end to end, largely in answer generation. B/C median total QA is much closer than their means. The observed reduction in retrieval time is only about 60 ms; it cannot explain the much larger difference in mean answer latency.','',
        '### 2. Warm Mandol: each stage','',
        f'**Mean {f(d["mean"])} ms; median {f(d["median"])} ms.** Dense embedding and reranking together account for approximately **{100*(de["mean"]+dr["mean"])/d["mean"]:.1f}%** of mean wall time. Their calls occur sequentially: embedding during hybrid retrieval, then reranking after candidates are collected.','']
    mandol=[
        ('Question / candidate-scope preparation','query_preparation_ms','Local; before hybrid search'),
        ('Dense text → vector API','embedding.total_ms','302.ai Qwen3-Embedding-0.6B, 1024D; network + provider time'),
        ('Dense vector similarity search','retrieval.dense_ms','Local; excludes the embedding API; includes nested lookups'),
        ('SPLADE query-vector calculation','retrieval.query_feature_metrics.vectors.splade.compute_time_ms','Local sparse encoder; INCLUDED in the SPLADE backend below'),
        ('SPLADE encoder + sparse search','__splade','Full backend; overlaps the dense branch'),
        ('BM25 query token/preparation','retrieval.query_feature_metrics.vectors.bm25.compute_time_ms','Local lexical preparation; INCLUDED in BM25 below'),
        ('BM25 preparation + lexical search','__bm25','Full backend; overlaps other retrieval work'),
        ('RRF fusion','retrieval.fusion_ms','Combine backend candidates'),
        ('MemoryUnit lookup','retrieval.memory_unit_lookup_ms','Nested inside backend searches; do not add again'),
        ('Candidate text / MemorySpace lookup','retrieval.candidate_space_lookup_ms','Prepare selected candidates and reranker inputs'),
        ('Cloud reranking','retrieval.rerank_ms','302.ai Qwen3-Reranker-0.6B; after hybrid search'),
        ('Warm engine readiness check','retrieval.retriever_readiness_check_ms','Tiny check; no model/index reload'),
        ('Hybrid-search wall subtotal','retrieval.Mandol_search_ms','INCLUDES dense embedding, backends and fusion'),
        ('TOTAL warm retrieval','retrieval.TOTAL_RETRIEVAL_MS','Independently measured wall time'),
    ]
    rows=[]
    for label,path,note in mandol:
        if path.startswith('__'):
            method=path[2:];v=stats(rounds['D'],lambda e:sum(x['latency_ms'] for x in e['retrieval']['backend_calls'] if x['method']==method))
        else:v=rstat('D',path)
        rows.append([label,f(v['mean']),f(v['median']),note])
    lines += [table(['Stage · N=10','Mean ms','Median ms','Scope'],rows),'',
        '**Do not add every row.** Query-vector computation is nested in its backend, MemoryUnit lookup is nested in search, and dense/sparse work overlaps. The hybrid subtotal is not an additional stage. The dense QueryBundle “compute time” is another wrapper around the same cloud embedding request—not a second dense embedding calculation.','',
        f'The local dense search averages only **{f(rstat("D","retrieval.dense_ms")["mean"])} ms**. Its speed does not establish an apples-to-apples advantage over StreamMeCo: D uses a different embedding model, 1024 rather than 3072 dimensions, and a different search representation.','',
        f'The reranker also explains the long tail: on Q{d_slow["question_index"]} it took **{d_slow["retrieval_rounds"][0]["retrieval"]["rerank_ms"]:,.1f} ms**, bringing total retrieval to **{total(d_slow):,.1f} ms**. Mean and median reranker timings are listed above. Ten samples are too few to infer a stable production tail. No initialization time needs to be subtracted from these totals—it was already excluded.','',
        '### 3. B/C one-shot: embedding versus similarity calculation','',
        '**Text embedding** means generating a vector from the query. **Vector similarity/search** means comparing that vector with stored memory vectors. They are different stages. “Embedding calculation” is not a third stage unless referring specifically to a separate encoder such as Mandol’s SPLADE.','']
    bc_specs=[
        ('Construct literal question query','query_construction_ms'),
        ('Prepare/back-translate query','query_preparation_ms'),
        ('Text → vector stage, including client overhead','embedding_ms'),
        ('Compare/search existing memory vectors','vector_search_ms'),
        ('StreamMeCo/TMR scoring','streammeco_tmr_scoring_ms'),
        ('Graph/node selection','graph_node_selection_ms'),
        ('Reranking — not used','retrieval.rerank_ms'),
        ('Sparse search — not used','retrieval.sparse_ms'),
        ('TOTAL one-shot retrieval','retrieval.TOTAL_RETRIEVAL_MS'),
    ]
    rows=[]
    for label,path in bc_specs:
        bs=rstat('B',path);cs=rstat('C',path);rows.append([label,f(bs['mean']),f(bs['median']),f(cs['mean']),f(cs['median'])])
    lines += [table(['Stage · N=10 per method','B mean ms','B median ms','C mean ms','C median ms'],rows),'',
        f'The OpenRouter API-call-only means are **{f(rstat("B","embedding.total_ms")["mean"])} ms (B)** and **{f(rstat("C","embedding.total_ms")["mean"])} ms (C)**; the slightly larger embedding-stage values above include local orchestration. These are API wall times, not isolated provider GPU inference times. The provider’s queue, network and model compute cannot be separated from these records.','',
        f'Embedding occupies about **{100*be["mean"]/b["mean"]:.1f}% of B** and **{100*ce["mean"]/c["mean"]:.1f}% of C** retrieval time. Local similarity search contributes most of the rest; scoring and graph selection are about a millisecond each. B/C use neither a sparse encoder nor a reranker.','',
        '### 4. Memory construction: mean and median for every recorded stage','',
        '**Optimized measurements only:** segments **27–144 (118 segments)**, after concurrent ASR, pooled HTTP, per-clip embedding batches and lookahead were enabled. Earlier-protocol segments 1–26 are excluded from this table. Clips have different durations, and outages, cache reuse and shared-GPU work occurred.','',
        'Means and medians are calculated independently for each row; medians of serial stages are not additive either. Times below are milliseconds. Null observations are omitted and counted in N; they are not assigned zero. ASR spans include any retries or cache lookup actually performed for the committed clip. Cached voice/face preprocessing can make a stage unavailable. These are observed stage spans, not estimates of uncached service cost.','']
    memory_specs=[
        ('Clip decoding','latency_ms.clip_decode'),
        ('Deepgram ASR span','latency_ms.deepgram_asr'),
        ('MAI ASR span','latency_ms.mai_transcribe_asr'),
        ('ASR stage wall time','latency_ms.asr_total'),
        ('Audio segmentation','latency_ms.audio_segmentation'),
        ('Speaker embedding · CAM++','latency_ms.speech_embedding_campplus'),
        ('Face detection/recognition','latency_ms.facial_detection_recognition_buffalo_l'),
        ('Face clustering','latency_ms.face_clustering'),
        ('VLM input/context preparation','stage_details.vlm.context_preparation_ms'),
        ('Gemini memory-generation API','latency_ms.vlm_memory_generation'),
        ('Memory-text embedding · batch after clip 26','latency_ms.text_embedding'),
        ('Graph updates · voice/face/text combined','latency_ms.graph_update_total'),
    ]
    rows=[]
    for label,path in memory_specs:
        ov=stats(opt,lambda x:get(x,path))
        rows.append([label,ov['n'],f(ov['mean']),f(ov['median'])])
    lines += [table(['Stage','Optimized N','Optimized mean ms','Optimized median ms'],rows),'',
        f'**Gemini is the main construction bottleneck:** optimized memory generation averages **{vlm["mean"]/1000:.2f} s** (median **{vlm["median"]/1000:.2f} s**), approximately **{100*vlm["mean"]/ordered["mean"]:.1f}%** of the mean ordered processing span. Mean graph-update time is only **{stats(opt,lambda x:x["latency_ms"].get("graph_update_total"))["mean"]/1000:.2f} s**.','',
        '**Means expose outages; medians show the typical case.** Optimized MAI spans have a 1.05-second median but a 4.28-second mean. Segments 65, 67 and 98 each spent roughly 122–125 seconds in MAI, including failed attempts/retries. Gemini itself also had long calls, including about 248 seconds on segment 84.','',
        '**The embedding optimization is visible, but not a controlled causal estimate:** earlier memory-text embedding averaged 2.15 seconds; optimized per-clip batches averaged 0.574 seconds. Clip contents, batch sizes, connection reuse and service conditions also differ, so do not attribute the entire difference to batching alone.','',
        '### 5. Why a prefetched clip can show ~200 seconds without taking ~200 seconds of model work','']
    rows=[]
    pipeline_specs=[('Preparation worker: trimming, decode and ASR','pipeline_timing.preparation_work_ms'),('Consumer waiting for preparation','pipeline_timing.consumer_wait_ms'),('Prepared clip waiting for chronological turn','pipeline_timing.ready_to_ordered_ms'),('Ordered processing through graph/audit work','ordered_processing_ms')]
    for label,path in pipeline_specs:
        v=stats(opt,lambda x:get(x,path));rows.append([label,v['n'],f(v['mean']/1000) if v['mean'] is not None else '—',f(v['median']/1000) if v['median'] is not None else '—'])
    for label,path in [('Ordered processing through persisted checkpoint','ordered_stage_ms'),('Full admission → persisted checkpoint','segment_latency_ms')]:
        v=stats(schedule,lambda x:x.get(path));rows.append([label,v['n'],f(v['mean']/1000),f(v['median']/1000)])
    lines += [table(['Optimized pipeline span','N','Mean seconds','Median seconds'],rows),'',
        'A future clip is admitted while earlier clips are still being processed. Its queue wait therefore counts toward admission-to-checkpoint latency. That is real latency, but it is not extra model inference and does not mean the pipeline completes only one clip every 200 seconds.','',
        'The median consumer wait is effectively zero: lookahead usually had the next clip ready. The roughly 122-second average ready-queue wait reflects the ordered Gemini stage being the bottleneck. Increasing lookahead further is unlikely to help much when preparation is already hidden; it can increase waiting and memory use.','',
        '**Deployment implication:** if new clips arrive every 30 seconds, the observed roughly 67-second mean ordered stage through checkpoint would not keep up with that arrival rate on one sequential memory worker. Lookahead hides preparation, but cannot remove the sustained Gemini bottleneck. This is a conditional inference from this run, not a separate live-stream benchmark; admission-to-checkpoint timing also does not measure any backlog before a clip is admitted.','',
        'Preparation overlaps work on other clips, so do not add it again to a segment’s queue/ordered total. The legacy `end_to_end_memory_generation_ms` field changed timing boundaries after optimization; a pooled mean of that field across all 144 clips would be misleading. The checkpoint event spans above are the consistent optimized end-to-end measurements. Pauses and restarts must be considered separately when estimating total experiment completion time.','',
        '**Reading the results:** C had the best observed score (6/10) and lowest mean retrieval time here, but ten questions and shared-GPU execution are insufficient for a general ranking. The actionable performance targets are Gemini generation for construction, embedding service latency for B/C, and embedding plus reranking service latency for D.','',
        '---','', '## Detailed measurements','']
    return lines
