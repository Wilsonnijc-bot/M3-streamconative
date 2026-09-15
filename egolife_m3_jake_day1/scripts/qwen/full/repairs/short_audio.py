from pathlib import Path
import ast,hashlib,json,datetime
r=Path('/opt/streammeco/run/egolife_10q_qwen35_4b_fps2_thinking_ids_v2_full')
s=r/'code/StreamMeCo';revision=r/'lineage/short_audio_boundary_fix';revision.mkdir(parents=True,exist_ok=True)
def function_span(text,name):
 node=next(n for n in ast.parse(text).body if isinstance(n,ast.FunctionDef) and n.name==name)
 return node.lineno-1,node.end_lineno
p=s/'mmagent/utils/video_processing.py';old=p.read_text();source=Path('/opt/streammeco/run/StreamMeCo/mmagent/utils/video_processing.py').read_text()
a,b=function_span(old,'process_video_clip');c,d=function_span(source,'process_video_clip')
if 'audio_duration_limit' not in old:
 (revision/'video_processing_before.py').write_text(old)
 lines=old.splitlines(keepends=True);lines[a:b]=source.splitlines(keepends=True)[c:d];p.write_text(''.join(lines))
p=s/'benchmarks/egolife_first10.py';old=p.read_text()
if 'audio_duration_limit=end-offset' not in old:
 (revision/'egolife_first10_before.py').write_text(old)
 old=old.replace("process_video_clip(str(actual), fps=PROCESSING_CONFIG['fps'])","process_video_clip(str(actual), fps=PROCESSING_CONFIG['fps'], audio_duration_limit=end-offset)")
 old=old.replace("process_video_clip(str(actual),fps=PROCESSING_CONFIG['fps'])","process_video_clip(str(actual),fps=PROCESSING_CONFIG['fps'],audio_duration_limit=end-offset)")
 p.write_text(old)
for name in ['pipeline_status.txt','launcher_status.txt','results/code_hashes.sha256']:
 p=r/name
 if p.exists() and not (revision/p.name).exists():(revision/p.name).write_bytes(p.read_bytes())
record={'recorded_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'reason':'MoviePy read beyond 30ms boundary slice at segment 98','change':'Reuse existing project sub-second FFmpeg audio decoder, bounded to planned segment duration. Normal-duration decoding unchanged.','checkpoint_sha256':hashlib.sha256((r/'work/build_state.pkl').read_bytes()).hexdigest(),'resume_from_segment':98,'preserved_skips':[23,39,50],'generation_prompt_fps_unchanged':True,'files':{str(p.relative_to(s)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [s/'mmagent/utils/video_processing.py',s/'benchmarks/egolife_first10.py']}}
(revision/'repair_manifest.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record))
