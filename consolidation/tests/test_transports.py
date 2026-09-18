"""Exercise real serialization/HTTP paths against a local test server, never a model."""
import json
import threading
import wave
from http.server import BaseHTTPRequestHandler,HTTPServer
import pytest
from consolidation.llm_consolidator import propose
from consolidation.moss_runner import run_moss,prepare_prefix
from consolidation.retrieval_refresh import APIEmbedder
from consolidation.common import read
from .test_system import fixture,patch,merge


@pytest.fixture
def server():
    requests=[]
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args): pass
        def do_POST(self):
            body=self.rfile.read(int(self.headers['Content-Length']))
            requests.append((self.path,body))
            if self.path.endswith('/chat/completions'):
                payload=json.loads(body)
                packet=json.loads(payload['messages'][1]['content'])
                result={'model':'test-server','choices':[{'finish_reason':'stop','message':{
                    'content':json.dumps(patch(packet,[merge()]))}}]}
            elif self.path.endswith('/embeddings'):
                result={'data':[{'index':i,'embedding':[1.,float(i)]} for i,_ in reversed(list(enumerate(json.loads(body)['input'])))]}
            else:
                result={'text':'[0][S01]Hi[1]','segments':[{'start':0,'end':1,'speaker':'S01','text':'Hi'}]}
            self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers()
            self.wfile.write(json.dumps(result).encode())
    http=HTTPServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
    yield 'http://127.0.0.1:'+str(http.server_port)+'/v1',requests
    http.shutdown();thread.join();http.server_close()


def test_llm_exact_request_and_response(server,tmp_path):
    endpoint,requests=server
    _,_,packet=fixture()
    result=propose(packet,tmp_path,'test-server',endpoint)
    assert result['decisions'][0]['op']=='merge_voice'
    assert json.loads(requests[0][1])==read(tmp_path/'llm_input.json')
    assert read(tmp_path/'llm_metadata.json')['backend']=='live'
    assert read(tmp_path/'llm_response.json')['model']=='test-server'


def test_moss_full_prefix_contract(server,tmp_path):
    endpoint,requests=server
    wav=tmp_path/'prefix.wav'
    with wave.open(str(wav),'wb') as out:
        out.setnchannels(1);out.setsampwidth(2);out.setframerate(16000)
        out.writeframes(b'\0\0'*16000)
    moss=run_moss(wav,'s',1,'s/moss_1',endpoint,tmp_path/'moss.json',revision='test')
    assert moss['segments'][0]['speaker']=='S01'
    assert moss['audio_sha256']
    assert b'max_new_tokens' in requests[0][1]
    with pytest.raises(ValueError):run_moss(wav,'s',2,'s/moss_2',endpoint,tmp_path/'bad.json')


def test_dense_api_restores_order(server):
    endpoint,_=server
    assert APIEmbedder(endpoint,'test').encode(['a','b'])==[[1.,0.],[1.,1.]]


def test_prefix_audio_preserves_gaps(tmp_path):
    import shutil
    if not shutil.which('ffmpeg'):
        pytest.skip('ffmpeg unavailable')
    for name in ('a.wav','b.wav'):
        with wave.open(str(tmp_path/name),'wb') as out:
            out.setnchannels(1);out.setsampwidth(2);out.setframerate(16000)
            out.writeframes(b'\x01\x00'*16000)
    replay={'origin_seconds':100,'segments':[
        {'absolute_start_seconds':100,'absolute_end_seconds':101,'start_seconds_in_source':0,'source':'a.wav'},
        {'absolute_start_seconds':102,'absolute_end_seconds':103,'start_seconds_in_source':0,'source':'b.wav'}]}
    path=prepare_prefix(replay,tmp_path,tmp_path/'prefix.wav')
    with wave.open(str(path),'rb') as audio:
        assert audio.getnframes()==48000
        pcm=audio.readframes(48000)
    assert pcm[32000:64000]==b'\x00\x00'*16000
    assert pcm[:32000]==pcm[64000:]==b'\x01\x00'*16000


def test_official_responses_preserves_model_reasoning_and_resume(tmp_path,monkeypatch):
    from consolidation.llm_consolidator import propose_official
    from consolidation.common import write
    import io
    _,_,packet=fixture()
    config=tmp_path/'api.json'
    write(config,{'gpt-6-astra':{'base_url':'','api_key':'test-key','reasoning_effort':'high'}})
    response={'id':'resp_test','status':'completed','model':'gpt-6-astra','usage':{'input_tokens':10,'output_tokens':5},
              'output':[{'type':'reasoning'}, {'type':'message','content':[{'type':'output_text','text':json.dumps(patch(packet,[merge()]))}]}]}
    requests=[]
    def request(req,timeout):
        requests.append(req)
        return io.BytesIO(json.dumps(response).encode())
    monkeypatch.setattr('urllib.request.urlopen',request)
    work=tmp_path/'work'
    assert propose_official(packet,work,config)['decisions'][0]['op']=='merge_voice'
    payload=read(work/'llm_input.json')
    assert payload['model']=='gpt-6-astra' and payload['reasoning']['effort']=='high'
    assert payload['background'] is True
    assert 'test-key' not in (work/'llm_input.json').read_text()
    propose_official(packet,work,config)
    assert requests[-1].full_url=='https://api.openai.com/v1/responses/resp_test'
    write(config,{'gpt-6-astra':{'base_url':'https://example.com/v1','api_key':'test-key'}})
    with pytest.raises(ValueError):propose_official(packet,work,config)
