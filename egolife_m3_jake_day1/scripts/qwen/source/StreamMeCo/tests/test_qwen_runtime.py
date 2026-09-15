import importlib.util,json
from pathlib import Path
import pytest
spec=importlib.util.spec_from_file_location('local_qwen_runtime_test',Path(__file__).parents[1]/'benchmarks/qwen_runtime.py')
r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
@pytest.mark.parametrize('model,finish,ok',[(r.MODEL,'stop',True),('gemini-3.8-flash','stop',False),(r.MODEL,'length',False)])
def test_local_identity_and_truncation(monkeypatch,tmp_path,model,finish,ok):
 seen=[]
 class Response:
  def raise_for_status(self):pass
  def json(self):return {'model':model,'returned_model':model,'finish_reason':finish,'response':'A'}
 def post(url,**kwargs):seen.append(url);return Response()
 monkeypatch.setattr(r.cloud_http,'post',post);monkeypatch.setenv('EGOLIFE_RESULTS',str(tmp_path))
 if ok:assert r.text_call('qwen','Question')['response']=='A'
 else:
  with pytest.raises(RuntimeError):r.text_call('qwen','Question')
 assert seen==['http://127.0.0.1:8766/generate']
 events=[json.loads(x) for x in (tmp_path/'qwen_calls.jsonl').read_text().splitlines()]
 assert len(events)==1 and ('error' in events[0])!=ok

def test_other_backends_rejected():
 with pytest.raises(RuntimeError):r.text_call('gemini','Question')

def test_configuration_cannot_mix_fps(monkeypatch,tmp_path):
 monkeypatch.setenv('QWEN_MODEL_PATH','/opt/streammeco/models/Qwen3.5-4B');monkeypatch.setenv('QWEN_VLM_FPS','2')
 r.configure(tmp_path,'build')
 monkeypatch.setenv('QWEN_VLM_FPS','1')
 with pytest.raises(RuntimeError):r.configure(tmp_path,'build')
