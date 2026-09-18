"""Process-local HTTP pools and accurately timed multi-text embedding requests."""
import atexit
import os
import json
from pathlib import Path
import threading
import time
import httpx

_lock=threading.Lock()
_clients={}
_counts={}
_local=threading.local()

def get_client(*,direct=False):
    with _lock:
        if direct not in _clients:
            _clients[direct]=httpx.Client(verify=not direct,trust_env=not direct,
                limits=httpx.Limits(max_connections=20,max_keepalive_connections=10,keepalive_expiry=120))
        return _clients[direct]

def post(url,*,direct=False,metrics=None,**kwargs):
    data=metrics if metrics is not None else {}
    with _lock:
        data['client_previously_used']=_counts.get(direct,0)>0
        _counts[direct]=_counts.get(direct,0)+1
    data.update(tcp_connect_count=0,tls_handshake_count=0)
    def trace(event,info):
        if event=='connection.connect_tcp.started':data['tcp_connect_count']+=1
        if event=='connection.start_tls.started':data['tls_handshake_count']+=1
    started=time.perf_counter()
    try:
        return get_client(direct=direct).post(url,extensions={'trace':trace},**kwargs)
    finally:
        data['http_wall_ms']=(time.perf_counter()-started)*1000
        _local.metrics=dict(data)

def clear_metrics():_local.metrics={}
def last_metrics():return dict(getattr(_local,'metrics',{}))

def close_clients():
    with _lock:
        for c in _clients.values():c.close()
        _clients.clear();_counts.clear()
atexit.register(close_clients)

def embed_batch(client,model,texts,*,timeout=120,attempts=2,metrics=None,sleep=time.sleep):
    texts=list(texts);metrics=metrics if metrics is not None else {}
    metrics.update(model=model,input_count=len(texts),input_chars=sum(map(len,texts)),
                   timing_scope='whole_batch',per_text_latency_ms=None,calls=[])
    if not texts:
        metrics.update(latency_ms=0,total_tokens=0);return [],0
    total=time.perf_counter()
    try:
        for attempt in range(1,attempts+1):
            start=time.perf_counter();event={'attempt':attempt,'request_start':time.time()}
            try:
                response=client.with_options(max_retries=0).embeddings.create(model=model,input=texts,timeout=timeout)
                items=sorted(response.data,key=lambda x:x.index)
                if [x.index for x in items]!=list(range(len(texts))):
                    raise ValueError('Embedding response indices do not match the requested batch')
                vectors=[x.embedding for x in items]
                tokens=response.usage.total_tokens if response.usage else None
                event.update(status='success',total_tokens=tokens)
                metrics['total_tokens']=tokens
                return vectors,tokens
            except Exception as exc:
                event.update(status='error',error=f'{type(exc).__name__}: {exc}')
                if attempt==attempts:
                    raise RuntimeError(f'Failed to get embedding batch after {attempts} attempts: {exc}') from exc
            finally:
                event.update(request_end=time.time(),latency_ms=(time.perf_counter()-start)*1000)
                metrics['calls'].append(event)
                root=os.environ.get('EGOLIFE_RESULTS')
                if root:
                    record={**event,'model':model,'segment_id':metrics.get('segment_id'),'input_count':len(texts),'timing_scope':'whole_batch'}
                    with _lock:
                        with (Path(root)/'embedding_batch_calls.jsonl').open('a') as handle:
                            handle.write(json.dumps(record,ensure_ascii=False)+'\n')
            sleep(min(2**attempt,10))
    finally:metrics['latency_ms']=(time.perf_counter()-total)*1000
