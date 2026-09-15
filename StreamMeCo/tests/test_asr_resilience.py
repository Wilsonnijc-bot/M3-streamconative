import importlib.util
import json
from pathlib import Path
import pytest
import httpx
spec=importlib.util.spec_from_file_location('asr_resilience',Path(__file__).parents[1]/'mmagent/utils/asr_resilience.py')
r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)

def test_success_cached_per_provider_and_audio(tmp_path):
    calls=[]
    def request():calls.append(1);return [{'asr':'hello'}]
    for provider,audio in [('deepgram',b'a'),('deepgram',b'a'),('mai',b'a'),('deepgram',b'b')]:
        assert r.transcribe_resilient(provider,audio,'wav',{},request,root=tmp_path)==[{'asr':'hello'}]
    assert len(calls)==3

def test_transient_retry_and_persistent_error(tmp_path):
    waits=[];calls=[]
    def request():
        calls.append(1)
        if len(calls)<3:raise r.ASRHTTPError('mai',503,'temporarily unavailable')
        return []
    assert r.transcribe_resilient('mai',b'a','wav',{},request,root=tmp_path,sleep=waits.append)==[]
    assert waits==[2,4]
    events=[json.loads(x) for x in (tmp_path/'asr_calls.jsonl').read_text().splitlines()]
    assert [e['status'] for e in events]==['error','error','success']
    assert events[0]['http_status']==503

def test_permanent_error_no_retry_and_redacts_key(tmp_path):
    def request():raise r.ASRHTTPError('mai',401,'bad credential SECRET')
    with pytest.raises(RuntimeError,match='401'):
        r.transcribe_resilient('mai',b'a','wav',{'api_key':'SECRET'},request,root=tmp_path,sleep=lambda _:pytest.fail('must not retry'))
    assert 'SECRET' not in (tmp_path/'asr_calls.jsonl').read_text()

def test_network_retries_are_bounded(tmp_path):
    calls=[]
    def request():calls.append(1);raise httpx.ReadTimeout('timeout')
    with pytest.raises(RuntimeError,match='attempt 3/3'):
        r.transcribe_resilient('mai',b'a','wav',{},request,retries=3,root=tmp_path,sleep=lambda _:None)
    assert len(calls)==3
    assert not list((tmp_path/'asr_cache').glob('*.json'))

def test_fallback_keeps_successful_provider_only():
    source=[{'asr':'hello','speaker':1}]
    result=r.merge_available({'deepgram-asr':source},lambda *_:pytest.fail('must not call two-provider merge'))
    assert result[0]['asr_sources']==['deepgram-asr']
    assert 'asr_sources' not in source[0]
    assert r.merge_available({},lambda *_:pytest.fail('no provider'))==[]
