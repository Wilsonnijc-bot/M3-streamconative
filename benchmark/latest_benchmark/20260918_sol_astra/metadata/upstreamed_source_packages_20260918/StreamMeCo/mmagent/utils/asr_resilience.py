"""Persist independent ASR successes and bounded, observable transient retries."""
import hashlib
import json
import os
import time
import tempfile
import threading
from pathlib import Path

import httpx
import cloud_http

_event_lock = threading.Lock()

class ASRHTTPError(RuntimeError):
    def __init__(self, provider, status_code, detail, retry_after=None):
        self.status_code = status_code
        self.retry_after = retry_after
        super().__init__(f'{provider} transcription HTTP {status_code}: {detail[:1000]}')

def transcribe_resilient(model, audio, audio_format, model_config, request, *,
                         retries=5, root=None, sleep=time.sleep, context=None):
    # Include effective settings without storing credentials in the cache key metadata.
    settings={k:v for k,v in model_config.items() if k not in {'api_key','api_key_env'}}
    audio_hash=hashlib.sha256(audio).hexdigest()
    key=hashlib.sha256(json.dumps([model,audio_format,settings,audio_hash],sort_keys=True).encode()).hexdigest()
    directory=Path(root) if root else None
    cache=directory/'asr_cache'/f'{key}.json' if directory else None
    def event(**details):
        item={**(context or {}),'provider':model,'audio_sha256':audio_hash,'audio_bytes':len(audio),**details}
        if directory:
            directory.mkdir(parents=True,exist_ok=True)
            with _event_lock:
                with (directory/'asr_calls.jsonl').open('a') as handle:
                    handle.write(json.dumps(item,ensure_ascii=False)+'\n')
        print('ASR_EVENT '+json.dumps(item,ensure_ascii=False),flush=True)
    if cache and cache.exists():
        saved=json.loads(cache.read_text())
        if saved['audio_sha256']!=audio_hash or saved['provider']!=model:
            raise RuntimeError('ASR cache provenance mismatch')
        event(status='cache_hit',segments=len(saved['segments']),latency_ms=0)
        return saved['segments']
    for attempt in range(1,retries+1):
        started=time.perf_counter()
        start_epoch=time.time()
        cloud_http.clear_metrics()
        try:
            result=request()
        except Exception as exc:
            code=getattr(exc,'status_code',None)
            transient=isinstance(exc,httpx.TransportError) or code in {408,429,500,502,503,504}
            detail=f'{type(exc).__name__}: {exc}'
            # Error responses sometimes echo submitted credentials. Never retain them.
            for value in (model_config.get('api_key'),os.environ.get(model_config.get('api_key_env',''))):
                if value:detail=detail.replace(value,'[REDACTED]')
            delay=min(2**attempt,30)
            try:delay=max(delay,min(float(getattr(exc,'retry_after',None)),60))
            except (TypeError,ValueError):pass
            will_retry=transient and attempt<retries
            event(status='error',attempt=attempt,request_start=start_epoch,request_end=time.time(),
                  latency_ms=(time.perf_counter()-started)*1000,http_status=code,
                  transport=cloud_http.last_metrics(),error=detail,will_retry=will_retry,retry_delay_seconds=delay if will_retry else 0)
            if not will_retry:
                raise RuntimeError(f"ASR provider '{model}' failed on attempt {attempt}/{retries}: {detail}") from exc
            sleep(delay)
            continue
        elapsed=(time.perf_counter()-started)*1000
        if cache:
            cache.parent.mkdir(parents=True,exist_ok=True)
            with tempfile.NamedTemporaryFile(mode='w',dir=cache.parent,delete=False) as handle:
                json.dump({'provider':model,'audio_sha256':audio_hash,'segments':result},handle,ensure_ascii=False)
                temp=Path(handle.name)
            temp.replace(cache)
        event(status='success',attempt=attempt,request_start=start_epoch,request_end=time.time(),
              latency_ms=elapsed,segments=len(result),transport=cloud_http.last_metrics())
        return result


def merge_available(results, merge_both):
    """Keep successful ASR; never claim a failed provider contributed text."""
    if len(results)==2:
        return merge_both(results['deepgram-asr'],results['openrouter-mai-transcribe-2'])
    if not results:
        return []
    provider,segments=next(iter(results.items()))
    return [dict(segment,asr_sources=[provider]) for segment in segments]

def concurrent_providers(providers, request):
    """Run independent providers together; return ordered results and wall timings."""
    from concurrent.futures import ThreadPoolExecutor
    def one(provider):
        started=time.perf_counter()
        try:return request(provider),None,(time.perf_counter()-started)*1000
        except Exception as exc:return None,f'{provider}: {type(exc).__name__}: {exc}',(time.perf_counter()-started)*1000
    started=time.perf_counter()
    with ThreadPoolExecutor(max_workers=len(providers)) as pool:
        futures={p:pool.submit(one,p) for p in providers}
        outcomes={p:f.result() for p,f in futures.items()}
    return ({p:v[0] for p,v in outcomes.items() if v[1] is None},
            [v[1] for v in outcomes.values() if v[1] is not None],
            {p:v[2] for p,v in outcomes.items()},(time.perf_counter()-started)*1000)
