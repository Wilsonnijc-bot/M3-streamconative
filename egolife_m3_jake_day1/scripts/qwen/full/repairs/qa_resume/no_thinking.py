import json
import shutil
from pathlib import Path
r=Path('/opt/streammeco/run/egolife_10q_qwen35_4b_fps2_thinking_ids_v2_full')
b=r/'lineage/qa_no_thinking'
b.mkdir(exist_ok=False)
for name in ['server.log','pipeline_status.txt','launcher_status.txt']:
    shutil.copy2(r/name,b/name)
for p in (r/'results').glob('method_*.jsonl'):
    shutil.move(str(p),str(b/p.name))
code=r/'code/StreamMeCo/benchmarks'
shutil.copy2(code/'qwen_multimodal_server.py',b/'qwen_multimodal_server.py')
shutil.copy2('/tmp/qwen_qa_fix/qwen_multimodal_server.py',code/'qwen_multimodal_server.py')
p=code/'qwen_runtime.py'
s=p.read_text().replace("'thinking':True,'max_new_tokens'", "'thinking':True,'qa_thinking':False,'max_new_tokens'")
p.write_text(s)
p=r/'results/model_manifest.json'
m=json.loads(p.read_text());m['generation']['qa_thinking']=False
p.write_text(json.dumps(m,indent=2)+'\n')
p=r/'results/qa_generation_repair.json'
m=json.loads(p.read_text());m.update(qa_thinking=False,memory_thinking=True,user_instruction='then try no thinking')
p.write_text(json.dumps(m,indent=2)+'\n')
