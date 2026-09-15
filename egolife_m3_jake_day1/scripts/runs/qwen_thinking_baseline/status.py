import json
from pathlib import Path
r=Path('/opt/streammeco/run/egolife_10q_qwen35_4b_fps2_thinking')
for n in ['launcher_status.txt','preflight_exit_status.txt','pipeline_status.txt']:
 p=r/n
 if p.exists(): print(n,p.read_text().strip())
for n in ['server_calls.jsonl','results/segment_schedule_events.jsonl']:
 p=r/n
 if not p.exists():continue
 for line in p.read_text().splitlines():
  x=json.loads(line)
  if n.startswith('server'):
   c=x.get('context') or {}
   print(json.dumps({'purpose':c.get('purpose'),'segment':c.get('segment_id'),'thinking':x.get('thinking_enabled'),'thinking_completed':x.get('thinking_completed'),'frames':x.get('video_frame_count'),'processed_images':x.get('processed_image_count'),'input_tokens':x.get('input_tokens'),'output_tokens':x.get('output_tokens'),'finish':x.get('finish_reason'),'generation_ms':x.get('timings',{}).get('cuda_generation_ms')}))
  else:print('SEGMENT',x['segment_id'],x['status'])
p=r/'results/segment_plan.json'
if p.exists():
 d=json.loads(p.read_text());print('PLAN',d['segments'],d['source_clips'])
