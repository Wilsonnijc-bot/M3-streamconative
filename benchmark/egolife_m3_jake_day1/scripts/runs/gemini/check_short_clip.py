import importlib.util,io,base64,wave
from pathlib import Path
path=Path('/opt/streammeco/run/StreamMeCo/mmagent/utils/video_processing.py')
spec=importlib.util.spec_from_file_location('short_video_check',path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
video,frames,audio=m.process_video_clip('/opt/streammeco/run/egolife_10q_gemini/work/segments/segment_0098.mp4',audio_duration_limit=.03)
assert video and len(frames)==1 and audio
with wave.open(io.BytesIO(base64.b64decode(audio))) as w:
 duration=w.getnframes()/w.getframerate()
 assert 0<duration<=.03+1/16000
 print('SHORT_BOUNDARY_DECODE_PASSED',len(frames),'frames',duration,'audio_seconds',flush=True)
