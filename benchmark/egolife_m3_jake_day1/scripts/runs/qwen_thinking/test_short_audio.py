from pathlib import Path
import base64,io,wave,importlib.util,json
from mmagent.utils.video_processing import process_video_clip
r=Path('/opt/streammeco/run/egolife_10q_qwen35_4b_fps2_thinking_ids_v2_full')
plan=json.loads((r/'results/segment_plan.json').read_text())['plan']
row=plan[97];limit=row['end']-row['start']
_,frames,audio=process_video_clip(str(r/'work/segments/segment_0098.mp4'),fps=5,audio_duration_limit=limit)
with wave.open(io.BytesIO(base64.b64decode(audio))) as f:
 duration=f.getnframes()/f.getframerate();assert f.getframerate()==16000
assert len(frames)==1 and 0<duration<=limit+1/16000,(len(frames),duration,limit)
print('SHORT_BOUNDARY_OK',len(frames),duration,limit,flush=True)
spec=importlib.util.spec_from_file_location('old_video',r/'lineage/short_audio_boundary_fix/video_processing_before.py');old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
row=plan[96];p=r/'work/segments/segment_0097.mp4'
if not p.exists():p=Path(row['source'])
a=old.process_video_clip(str(p),fps=5);b=process_video_clip(str(p),fps=5,audio_duration_limit=row['end']-row['start'])
assert a==b
print('NORMAL_CLIP_BYTES_UNCHANGED',len(a[1]),flush=True)
