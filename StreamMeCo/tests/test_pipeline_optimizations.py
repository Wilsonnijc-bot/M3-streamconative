import sys
from pathlib import Path
from types import SimpleNamespace
from threading import Barrier,Event
import importlib.util
import pytest
sys.path.insert(0,str(Path(__file__).parents[1]))
import cloud_http
spec=importlib.util.spec_from_file_location('asr_opt',Path(__file__).parents[1]/'mmagent/utils/asr_resilience.py')
a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
from benchmarks.segment_prefetch import SegmentPrefetch

def test_asr_requests_overlap_and_preserve_provider_order():
    barrier=Barrier(2)
    def request(p):barrier.wait(timeout=2);return [p]
    results,errors,times,total=a.concurrent_providers(['deepgram','mai'],request)
    assert list(results)==['deepgram','mai'] and not errors
    assert all(t>=0 for t in times.values()) and total>=max(times.values())

def test_embedding_batch_preserves_indices_and_has_no_fake_per_text_timing():
    requests=[]
    class Client:
        def with_options(self,**kw):assert kw=={'max_retries':0};return self
        @property
        def embeddings(self):return self
        def create(self,**kw):
            requests.append(kw)
            return SimpleNamespace(data=[SimpleNamespace(index=1,embedding=[2]),SimpleNamespace(index=0,embedding=[1])],usage=SimpleNamespace(total_tokens=4))
    metrics={};vectors,tokens=cloud_http.embed_batch(Client(),'model',['first','second'],metrics=metrics)
    assert vectors==[[1],[2]] and len(requests)==1 and requests[0]['input']==['first','second']
    assert tokens==4 and metrics['per_text_latency_ms'] is None and len(metrics['calls'])==1
    assert metrics['latency_ms']>=metrics['calls'][0]['latency_ms']

def test_http_pool_reused_but_actual_connects_measured(monkeypatch):
    cloud_http.close_clients();created=[]
    class Client:
        def __init__(self,**kw):created.append(kw)
        def post(self,url,**kw):
            kw['extensions']['trace']('connection.connect_tcp.started',{})
            return 'response'
        def close(self):pass
    monkeypatch.setattr(cloud_http.httpx,'Client',Client)
    first={};second={}
    cloud_http.post('http://test',metrics=first);cloud_http.post('http://test',metrics=second)
    assert len(created)==1 and first['client_previously_used'] is False and second['client_previously_used'] is True
    assert second['tcp_connect_count']==1 # reuse of client does not imply reuse of TCP
    cloud_http.close_clients()

def test_prefetch_is_bounded_and_consumed_in_order():
    barrier=Barrier(3);seen=[]
    def prepare(row,index):
        seen.append(index)
        if index<=3:barrier.wait(timeout=2)
        return {'index':index}
    prefetch=SegmentPrefetch(list(range(6)),prepare,ahead=2)
    try:
        first=prefetch.get(1)
        assert first['index']==1 and set(seen)=={1,2,3}
        assert len(prefetch.futures)==2
        assert first['pipeline_timing']['consumer_wait_ms']>=0
        assert prefetch.get(2)['index']==2
    finally:prefetch.close()
