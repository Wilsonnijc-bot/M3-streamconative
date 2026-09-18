import json
import shutil
from pathlib import Path

r = Path('/opt/streammeco/run/egolife_10q_qwen35_4b_fps2_thinking_ids_v2_full')
backup = r / 'lineage/qa_thinking_loop_fix'
backup.mkdir(parents=True, exist_ok=False)
code = r / 'code/StreamMeCo/benchmarks'
for name in ['qwen_runtime.py', 'qwen_multimodal_server.py']:
    shutil.copy2(code / name, backup / name)
    shutil.copy2(Path('/tmp/qwen_qa_fix') / name, code / name)
for name in ['verify_resume.py', 'pipeline_status.txt', 'launcher_status.txt', 'server.log']:
    shutil.copy2(r / name, backup / name)
p = r / 'verify_resume.py'
s = p.read_text()
s = s.replace("assert (r/'code/StreamMeCo'/name).read_bytes()==(source/'code/StreamMeCo'/name).read_bytes()", "candidate = r/'lineage/qa_thinking_loop_fix/qwen_multimodal_server.py' if name=='benchmarks/qwen_multimodal_server.py' else r/'code/StreamMeCo'/name\n assert candidate.read_bytes()==(source/'code/StreamMeCo'/name).read_bytes()")
p.write_text(s)
p = r / 'results/model_manifest.json'
shutil.copy2(p, backup / 'model_manifest.json')
m = json.loads(p.read_text())
m['generation']['text_repetition_penalty'] = 1.08
p.write_text(json.dumps(m, indent=2)+'\n')
p = code / 'qwen_runtime.py'
p.write_text(p.read_text().replace("'text_repetition_penalty':1.0", "'text_repetition_penalty':1.08"))
(r/'results/qa_generation_repair.json').write_text(json.dumps({'reason':'QA controller thinking repetition exhausted 16384 tokens before answer', 'thinking':True,'qa_repetition_penalty':1.08,'qa_system_prompt':'See benchmarks/qwen_runtime.py text_call', 'memory_generation_changed':False,'prior_code_and_manifest':str(backup)},indent=2)+'\n')
