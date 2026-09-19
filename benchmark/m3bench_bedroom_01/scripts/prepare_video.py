"""Materialize chronological 30-second source windows without using QA content."""
import json,subprocess,hashlib,math
from pathlib import Path
root=Path('/opt/streammeco/run/m3bench_bedroom_gemini')
source=Path('/opt/streammeco/data/m3bench_bedroom/bedroom_01.mp4')
clips=source.parent/'clips';clips.mkdir(exist_ok=True)
def probe(p):
 return json.loads(subprocess.check_output(['ffprobe','-v','error','-show_format','-show_streams','-of','json',str(p)]))
meta=probe(source);duration=float(meta['format']['duration'])
plan=[]
for i,start in enumerate(range(0,math.ceil(duration),30),1):
 end=min(duration,start+30);clock=f'{start//3600:02d}{start//60%60:02d}{start%60:02d}00'
 target=clips/f'bedroom_01_{clock}.mp4'
 if not target.exists():
  tmp=target.with_suffix('.partial.mp4')
  subprocess.run(['ffmpeg','-nostdin','-v','error','-y','-ss',str(start),'-i',str(source),'-t',str(end-start),'-map','0:v:0','-map','0:a:0','-c:v','libx264','-preset','veryfast','-crf','18','-threads','2','-c:a','aac','-b:a','128k',str(tmp)],check=True)
  tmp.replace(target)
 measured=float(probe(target)['format']['duration'])
 assert abs(measured-(end-start))<.15,(target,measured)
 plan.append(dict(segment_id=i,source=str(source),start=start,end=end,clip=str(target),encoded_duration=measured))
 print(f'PREPARED_CLIP {i}/{math.ceil(duration/30)} {start:.3f}:{end:.3f}',flush=True)
# End-of-video queries: exact original duration; clamp final container boundary if encoding trims samples.
query_end=min(duration,plan[-1]['start']+plan[-1]['encoded_duration'])
rows=json.loads((root/'questions_reference.json').read_text())
requested={f'Q{i:02d}':2163.0 for i in range(1,16)}
requested.update(Q09=102.0,Q01=440.0,Q08=440.0,Q10=705.0,Q11=1265.0)
for row in rows:
 effective=90.0 if row['ID']=='Q09' else requested[row['ID']]
 row.update(query_time={'date':'VIDEO','time':effective},requested_query_seconds=requested[row['ID']],effective_query_seconds=effective,timestamp_approximation_seconds=effective-requested[row['ID']])
(root/'questions.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
(root/'results').mkdir(exist_ok=True)
digest=hashlib.sha256()
with source.open('rb') as handle:
 for block in iter(lambda:handle.read(8*1024*1024),b''):digest.update(block)
manifest=dict(source_url='https://huggingface.co/datasets/ByteDance-Seed/M3-Bench/resolve/main/videos/robot/bedroom_01.mp4',source_sha256=digest.hexdigest(),source_metadata=meta,duration_seconds=duration,query_end_seconds=query_end,segment_count=len(plan),plan=plan,streaming='offline chronological replay; ordered state updates, two-segment lookahead; no real-time pacing')
(root/'results/segment_plan.json').write_text(json.dumps(manifest,indent=2)+'\n')
