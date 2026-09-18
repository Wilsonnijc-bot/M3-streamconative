"""Mandol venv worker: one build for one snapshot, one search per question."""
import argparse
import os
from pathlib import Path
import sys
import time
from bench_common import ROOT, atomic, read, sha
sys.path.insert(0,str(ROOT/'source/Mandol/src'))

def main():
    p=argparse.ArgumentParser();p.add_argument('--snapshot',type=Path,required=True);p.add_argument('--serve',action='store_true');a=p.parse_args()
    folder=a.snapshot;req=read(folder/'mandol_request.json');start=time.perf_counter()
    if read(folder/'export/manifest.json')['source_graph_sha256']!=req['snapshot_sha256']:raise ValueError('Mandol export snapshot differs from R1')
    from mandol.adapters.m3.adapter import M3MandolAdapter,M3MandolConfig
    from mandol.adapters.m3.retriever import M3MandolRetriever
    from mandol.utils.model_manager import global_model_manager
    if global_model_manager.get_splade_model() is None:raise RuntimeError('SPLADE unavailable')
    from mandol.adapters.m3.embedding import OpenAICompatible302EmbeddingAdapter
    dense_timings=[];dense_errors=[]
    original_encode=OpenAICompatible302EmbeddingAdapter.encode
    def measured_encode(self,*args,**kwargs):
        began=time.perf_counter()
        try:return original_encode(self,*args,**kwargs)
        except Exception as error:
            dense_errors.append(type(error).__name__);raise
        finally:dense_timings.append((time.perf_counter()-began)*1000)
    OpenAICompatible302EmbeddingAdapter.encode=measured_encode
    configuration=read(ROOT/'configs/mandol.json');settings=configuration['mandol']
    output=folder/'mandol'
    manifest=folder/'mandol_build.json'
    if not manifest.exists():
        if output.exists():
            raise RuntimeError('incomplete Mandol build requires explicit repair, refusing mixed index')
        t=time.perf_counter();build=M3MandolAdapter.build(folder/'export',output,M3MandolConfig(**settings))
        atomic(manifest,dict(snapshot_sha256=req['snapshot_sha256'],build_ms=(time.perf_counter()-t)*1000,dense_embedding_ms=sum(dense_timings),manifest=build))
    elif read(manifest)['snapshot_sha256']!=req['snapshot_sha256']:raise ValueError('Mandol snapshot changed')
    t=time.perf_counter();retriever=M3MandolRetriever.load(output)
    from mandol.retrieval.retrieval_interface import RetrievalMethod
    indexes=retriever.graph.get_multi_retriever()
    for method in (RetrievalMethod.BM25,RetrievalMethod.COSINE_SIMILARITY,RetrievalMethod.SPLADE):
        indexes._ensure_retriever_loaded(method)
    for method in (RetrievalMethod.BM25,RetrievalMethod.SPLADE):
        if not getattr(indexes.retrievers[method],'_index_built',False):raise RuntimeError('persisted hybrid index not ready')
    component_metrics=[]
    for method in (RetrievalMethod.BM25,RetrievalMethod.COSINE_SIMILARITY,RetrievalMethod.SPLADE):
        component=indexes.retrievers[method];original=component.search
        def measured_search(*args,_original=original,_name=method.name,**kwargs):
            begin=time.perf_counter();record=dict(method=_name,status='error')
            try:
                found=_original(*args,**kwargs);record.update(status='success',count=len(found));return found
            finally:
                record['duration_ms']=(time.perf_counter()-begin)*1000;component_metrics.append(record)
        component.search=measured_search
    retriever.prepare_reranker_302(configuration['reranking'])
    load_ms=(time.perf_counter()-t)*1000
    atomic(folder/'mandol_initialization.json',dict(index_reload_and_warmup_ms=load_ms,reranker=configuration['reranking'],excluded_from_warm_retrieval=True))
    if a.serve: print('BENCH_READY',flush=True)
    def requests():
        if not a.serve: yield from req['questions']; return
        import json
        for line in sys.stdin:
            command=json.loads(line)
            if command.get('stop'):break
            yield command
    for q in requests():
        result=folder/'mandol_search'/f"{q['question_id']}.json"
        if result.exists():
            if a.serve: print('BENCH_RESULT '+str(result),flush=True)
            continue
        dense_timings.clear();dense_errors.clear();component_metrics.clear();began=time.perf_counter();wall=time.time()
        evidence=retriever.search(q['question'],top_k=10,enable_graph_expansion=False,rerank_method=configuration['reranking']['method'])
        elapsed=(time.perf_counter()-began)*1000
        if dense_errors or any(r['status']!='success' for r in component_metrics):raise RuntimeError('hybrid retrieval component failed')
        if retriever._candidate_uids(None) and {r['method'] for r in component_metrics}!={'BM25','COSINE_SIMILARITY','SPLADE'}:raise RuntimeError('not all three hybrid methods ran')
        atomic(result,dict(snapshot_sha256=req['snapshot_sha256'],evidence=evidence,retrieval_calls=1,
            retrieval_ms=elapsed,dense_embedding_ms=sum(dense_timings),start_ts=wall,end_ts=time.time(),load_ms=load_ms,
            method='BM25+dense+SPLADE; RRF; Qwen reranking via 302; graph expansion disabled',
            metrics=dict(retriever.last_search_metrics,components=list(component_metrics)),
            component_timings_note='Adapter search exposes combined fusion/search/lookup wall time; missing component timings are not zero.'))
        if a.serve: print('BENCH_RESULT '+str(result),flush=True)
    retriever.reranker_302.close()
    print('MANDOL_SNAPSHOT_READY',req['snapshot_sha256'],len(req['questions']),flush=True)

if __name__=='__main__':main()
