import importlib.util
import json
from pathlib import Path
import pytest

spec=importlib.util.spec_from_file_location('gemini_runtime_test',Path(__file__).parents[1]/'benchmarks/gemini_runtime.py')
r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)

@pytest.mark.parametrize('returned,finish,ok',[(r.MODEL,'stop',True),('wrong-model','stop',False),(r.MODEL,'length',False)])
def test_model_identity_and_truncation_fail_closed(monkeypatch,tmp_path,returned,finish,ok):
    seen=[]
    class Response:
        def raise_for_status(self): pass
        def json(self):return {'model':returned,'choices':[{'finish_reason':finish,'message':{'content':'A'}}],'usage':{'prompt_tokens':3,'completion_tokens':1}}
    class Client:
        def __init__(self,**kwargs):pass
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def post(self,*args,**kwargs):seen.append(kwargs['json']);return Response()
    monkeypatch.setenv('API_302_KEY','fake')
    monkeypatch.setenv('EGOLIFE_RESULTS',str(tmp_path))
    monkeypatch.setattr(r.cloud_http,'post',lambda *a,**kw: Client().post(*a,**kw))
    if ok: assert r.text_call('gemini','question')['response']=='A'
    else:
        with pytest.raises(RuntimeError):r.text_call('gemini','question')
    events=[json.loads(x) for x in (tmp_path/'gemini_calls.jsonl').read_text().splitlines()]
    assert len(events)==len(seen)==1
    assert seen[0]['model']==r.MODEL
    assert events[0]['request_end']>=events[0]['request_start']
    assert events[0]['latency_ms']>=0
    assert ('error' in events[0]) != ok

def test_qwen_rejected_before_network():
    with pytest.raises(RuntimeError,match='Gemini only'):r.text_call('qwen','question')
