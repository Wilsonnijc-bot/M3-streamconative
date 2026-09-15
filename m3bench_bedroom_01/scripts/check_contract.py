"""Verify open-ended answers, no reference leakage, and unchanged retrieval code."""
import os,sys,json,ast,tempfile
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,os.environ['STREAMMECO_ROOT'])
from benchmarks import bedroom_benchmark as b
question={'id':'test','query_time':{'date':'VIDEO','time':2163.264},'question':'What is the occupation?'}
prompts=[]
b.run_retrieval=lambda *args: ({'CLIP_1':['Someone is a designer.']},[],{'evidence':[],'returned_node_ids':[]})
def call(backend,prompt,*args):
 prompts.append(prompt)
 return {'response':'A designer.','latency_ms':1}
b.model_call=call
result=b.one_shot(None,question,'gemini',SimpleNamespace(top_k=2,qwen_url='unused'))
assert result['prediction']=='A designer.'
assert 'one letter' not in prompts[0] and 'multiple-choice' not in prompts[0]
qa=dict(ID='test',question='What is the occupation?',query_time=question['query_time'],answer='SECRET_REFERENCE_NEVER_SENT')
assert 'SECRET_REFERENCE_NEVER_SENT' not in json.dumps(b.public_question(qa))
assert b.clock_seconds(2163.264)==2163.264
assert b.clock_seconds('00360000')==2160
with tempfile.TemporaryDirectory() as t:
 p=Path(t)/'questions.json';p.write_text(json.dumps([dict(qa,ID=f'Q{i:02d}') for i in range(1,16)]))
 private,public=b.load_questions(p)
 assert len(public)==15 and all('answer' not in r and 'choices' not in r for r in public)
# Retrieval selection, controller control flow, prefetch and memory building remain the baseline algorithms.
original=ast.parse(Path('/opt/streammeco/run/StreamMeCo/benchmarks/egolife_first10.py').read_text())
new=ast.parse(Path(b.__file__).read_text())
def f(tree,name):return ast.dump(next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name),include_attributes=False)
for name in ['run_retrieval','normal_controller','build_memory','process_one_segment','_process_one_segment','compress_snapshots']:
 assert f(original,name)==f(new,name),name
print('PASS: free-text preservation; no gold/choices in public question; all 15 questions; elapsed clock; unchanged retrieval/controller/build/compression',flush=True)
