from pathlib import Path
import shutil
base=Path(__file__).parent
s=base/'source/StreamMeCo'
def edit(rel, pairs):
 p=s/rel;t=p.read_text()
 for a,b in pairs:
  assert a in t,(rel,a);t=t.replace(a,b)
 p.write_text(t)
edit('benchmarks/egolife_first10.py', [('os.environ["EGOLIFE_GEMINI_ONLY"] = "1"','os.environ.pop("EGOLIFE_GEMINI_ONLY", None)\nos.environ["EGOLIFE_QWEN_ONLY"] = "1"'),('gemini_runtime','qwen_runtime'),('gemini_report','qwen_report'),('"gemini"','"qwen"'),('gemini_calls','qwen_calls'),('gemini_latency_ms','qwen_latency_ms'),('non-Gemini','incompatible Qwen')])
edit('m3_agent/memorization_memory_graphs.py',[('if os.environ.get("EGOLIFE_GEMINI_ONLY") == "1":','if os.environ.get("EGOLIFE_QWEN_ONLY") == "1":\n    from mmagent.memory_processing_local_qwen import process_memories, generate_memories\nelif os.environ.get("EGOLIFE_GEMINI_ONLY") == "1":')])
edit('mmagent/utils/chat_api.py',[('if os.environ.get("EGOLIFE_GEMINI_ONLY") == "1":','if os.environ.get("EGOLIFE_GEMINI_ONLY") == "1" or os.environ.get("EGOLIFE_QWEN_ONLY") == "1":')])
edit('benchmarks/segment_resilience.py',[("'Gemini returned empty/truncated',", "'Gemini returned empty/truncated', 'Qwen returned empty/truncated', 'Qwen generation failed:',")])
t=(s/'benchmarks/gemini_report.py').read_text().replace('gemini-3.8-flash','Qwen/Qwen3.5-4B').replace('Gemini','Qwen').replace('gemini','qwen').replace('via 302.ai.','locally on CUDA at 2 FPS (model-only comparison).')
(s/'benchmarks/qwen_report.py').write_text(t)
t=(s/'mmagent/memory_processing_gemini.py').read_text().replace('gemini_runtime','qwen_runtime').replace("messages, media = generate_messages(","messages, media = generate_messages(").replace("] + context)","] + context, fps=float(__import__('os').environ.get('QWEN_VLM_FPS','2')))")
t=t.replace("event = runtime.call(messages, 'memory_construction')", "event = runtime.call(messages, 'memory_construction', media=media)")
(s/'mmagent/memory_processing_local_qwen.py').write_text(t)
