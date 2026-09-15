import json,re
from pathlib import Path
r=Path('/opt/streammeco/run/egolife_10q_qwen35_4b_fps2_thinking')
calls=[json.loads(l) for l in (r/'server_calls.jsonl').read_text().splitlines()]
commits={x['segment_id']:x for x in [json.loads(l) for l in (r/'results/segment_schedule_events.jsonl').read_text().splitlines()]}
rows=[]
for x in calls:
 c=x.get('context') or {};i=c.get('segment_id')
 if c.get('purpose')!='memory_construction' or i not in [1,2,3]:continue
 text=x['response'].strip();text=re.sub(r'^```(?:json)?\s*','',text);text=re.sub(r'\s*```$','',text)
 memory=json.loads(text)
 assert x['thinking_enabled'] and x['thinking_completed'] and x['finish_reason']=='stop'
 assert x['processed_image_count']==x['submitted_image_count']
 assert x['video_frame_count']==c['media']['frame_count']
 assert x['vlm_fps']==2.0 and commits[i]['status']=='committed'
 assert memory['video_description'] and memory['high_level_conclusions']
 rows.append({'segment_id':i,'video_frames':x['video_frame_count'],'processed_images':x['processed_image_count'],'thinking_completed':True,'output_tokens_including_thinking':x['output_tokens'],'generation_seconds':x['timings']['cuda_generation_ms']/1000,'episodic_count':len(memory['video_description']),'semantic_count':len(memory['high_level_conclusions']),'truncated':False,'committed':True})
assert sorted(x['segment_id'] for x in rows)==[1,2,3]
result={'status':'passed','scope':'first-three-segment structured construction preflight; not an accuracy or full-run guarantee','model':'Qwen/Qwen3.5-4B','vlm_fps':2,'thinking_enabled':True,'max_new_tokens':16384,'concurrent_gpu':True,'segments':rows}
(r/'results/fps_thinking_preflight.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
