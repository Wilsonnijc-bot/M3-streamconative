"""Fail-closed 302 Qwen reranking transport; called inside one M3 adapter search."""
import hashlib
import math
import os
import time
import httpx

class Reranker302:
    def __init__(self,config):
        self.config=config
        if config['endpoint']!='https://api.302.ai/v1/rerank':raise ValueError('reranker requires the audited 302 endpoint')
        self.client=httpx.Client(timeout=config.get('timeout_s',60),headers={'Authorization':'Bearer '+os.environ[config['api_key_env']]})
    def rerank(self,query,ranked):
        if not ranked:return [],dict(calls=0,reranking_ms=0.,status='empty_candidates')
        documents=[unit.raw_data.get('text_content',unit.text_cached) for unit,score in ranked]
        payload=dict(model=self.config['model'],query=query,documents=documents,top_n=len(documents),return_documents=False)
        started=time.perf_counter();wall=time.time()
        response=self.client.post(self.config['endpoint'],json=payload);response.raise_for_status();body=response.json()
        results=body.get('results',body.get('data'))
        if not isinstance(results,list):raise ValueError('invalid 302 reranking response')
        indices=[int(r['index']) for r in results]
        if sorted(indices)!=list(range(len(documents))):raise ValueError('incomplete/duplicate reranking indices')
        scored=[(ranked[int(r['index'])][0],float(r['relevance_score'])) for r in results]
        if not all(math.isfinite(score) for _,score in scored):raise ValueError('non-finite reranking score')
        scored.sort(key=lambda item:(-item[1],item[0].uid))
        return scored,dict(calls=1,reranking_ms=(time.perf_counter()-started)*1000,start_ts=wall,end_ts=time.time(),
            status='success',endpoint=self.config['endpoint'],model=self.config['model'],candidate_count=len(documents),
            document_sha256=[hashlib.sha256(t.encode()).hexdigest() for t in documents],candidate_uids=[u.uid for u,s in ranked],
            pre_rerank_scores=[float(s) for u,s in ranked],request_payload=payload,raw_response=body)
    def close(self):self.client.close()
