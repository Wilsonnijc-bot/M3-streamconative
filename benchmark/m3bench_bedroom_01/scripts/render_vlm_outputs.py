"""Readable per-clip model outputs, distinct from committed graph state."""
from pathlib import Path
import json,re,os,hashlib

def read(path,default=None):
 try:return json.loads(path.read_text())
 except (OSError,json.JSONDecodeError):return default

def records(path):
 if not path.exists():return []
 rows=[]
 for line in path.read_text(errors='replace').splitlines():
  try:rows.append(json.loads(line))
  except json.JSONDecodeError:pass
 return rows

def literal(text):
 length=max([len(m.group()) for m in re.finditer(r'`+',text)]+[2])+1
 fence='`'*max(3,length)
 return fence+'text\n'+text+'\n'+fence

def clean(text):return re.sub(r'<((?:voice|face|character)_[^>]+)>',r'`\1`',str(text))
def link(path,folder,label):return '['+label+']('+os.path.relpath(path,folder)+')'
def ms(value):return '—' if value is None else f'{value:,.2f}'
def write(path,text):
 path.parent.mkdir(parents=True,exist_ok=True);temp=path.with_suffix(path.suffix+'.tmp');temp.write_text(text.rstrip()+'\n');temp.replace(path)

def render(raw,out,case,committed):
 root=raw/'results' if (raw/'results').exists() else raw
 audit_paths={};audits={}
 for p in (root/'clip_audits').glob('*_audit.json'):
  a=read(p)
  if a:audits[int(a['clip_id'])]=a;audit_paths[int(a['clip_id'])]=p
 for p in [raw/'provenance/memory_construction_latency.jsonl']:
  for a in records(p):
   if 'clip_id' in a:audits[int(a['clip_id'])]=a;audit_paths[int(a['clip_id'])]=p
 calls={};call_sources=[]
 for p in [root/'gemini_calls.jsonl',root/'qwen_calls.jsonl',raw/'provenance/memory_gemini_calls.jsonl']:
  if not p.exists():continue
  call_sources.append(p)
  for event in records(p):
   segment=event.get('segment_id',event.get('clip_id'))
   if segment is not None and 'memory' in event.get('purpose',''):
    calls.setdefault(int(segment),[]).append(event)
 source_map={}
 for i,row in enumerate(read(root/'segment_plan.json',{}).get('plan',[]),1):
  source_map[i]={'source':Path(row['source']).name,'start_seconds_in_source':row['start'],'end_seconds_in_source':row['end']}
 for p in (root/'memory').glob('q*/metadata.json'):
  for row in read(p,{}).get('source_segments',[]):source_map[int(row['segment_id'])]=row
 for p in [*raw.glob('*.log'),*(raw/'provenance').glob('*.log')]:
  text=p.read_text(errors='replace')
  for match in re.finditer(r'SEGMENT_(COMPLETE|SKIPPED) id=(\d+) source=(\S+) range=([\d.]+):([\d.]+)',text):
   kind,i,name,start,end=match.groups();i=int(i)
   source_map.setdefault(i,{'source':name,'start_seconds_in_source':float(start),'end_seconds_in_source':float(end)})
   if kind=='COMPLETE':committed.add(i)
 skipped={int(x['segment_id']):x for x in records(root/'api_failures.jsonl') if x.get('status')=='skipped_api_failure' and 'segment_id' in x}
 entries=[]
 for i in sorted(set(audits)|set(calls)):
  a=audits.get(i,{})
  v=a.get('stage_details',{}).get('vlm',{})
  all_calls=calls.get(i,[])+[x for x in v.get('attempts',[]) if isinstance(x,dict)]
  unique={}
  for e in all_calls:
   key=e.get('call_id') or hashlib.sha256(json.dumps(e,sort_keys=True).encode()).hexdigest()
   unique[key]=e
  attempts=list(unique.values());attempts.sort(key=lambda x:x.get('request_start',0))
  parsed=a.get('generated_memory',v.get('generated_memory',{}))
  raw_response=v.get('raw_response') or next((e.get('response') for e in reversed(attempts) if e.get('response')),None)
  status='Skipped after recorded failure' if i in skipped else 'Committed' if i in committed else 'Saved audit; checkpoint not confirmed' if a else 'Attempted; no committed memory audit'
  entries.append({'name':f'clip_{i:04d}','clip':i,'audit':a,'vlm':v,'attempts':attempts,'memory':parsed,'raw_response':raw_response,'status':status,'source':source_map.get(i,{'source':a.get('clip_path','not recorded')}),'audit_path':audit_paths.get(i)})
 # First-clip comparison artifacts contain two explicitly separate model branches.
 if not entries and case.startswith('first_clip_'):
  shared=read(raw/'shared_preprocessing.json',{})
  for p in sorted(raw.glob('*.json')):
   x=read(p,{})
   if not isinstance(x,dict) or 'vlm_ms' not in x:continue
   memory=x.get('memory',{})
   response=x.get('raw_memory')
   if not isinstance(response,str):response=json.dumps(response,ensure_ascii=False,indent=2) if response else None
   entries.append({'name':'clip_0001_'+p.stem,'clip':1,'audit':{},'vlm':{'vlm_ms':x['vlm_ms'],'valid_memory_json':bool(memory)},'attempts':[],'memory':memory,'raw_response':response,'status':'Saved first-clip comparison output','source':{'source':shared.get('clip','see source')},'audit_path':p,'model':x.get('model')})
 destination=out/'vlm_outputs';destination.mkdir(exist_ok=True)
 provenance=raw.parents[1]/'vlm_outputs'/case;provenance.mkdir(parents=True,exist_ok=True)
 index=['# Per-clip VLM outputs','',
        'These are model-generated descriptions and conclusions **before graph integration**. They are not the accumulated memory graph. Read [committed memories](../memories.md) separately. Failed/retried outputs are retained, and a generated response is not automatically a committed segment.','',
        '| Clip | Source | State | Episodic | Semantic | VLM ms | Recorded attempts |',
        '| --- | --- | --- | ---: | ---: | ---: | ---: |']
 for e in entries:
  a=e['audit'];v=e['vlm'];attempts=e['attempts'];memory=e['memory'] if isinstance(e['memory'],dict) else {}
  episodic=memory.get('video_description',memory.get('video_descriptions',[]));semantic=memory.get('high_level_conclusions',[])
  source=e['source'];model=e.get('model') or a.get('reasoning_model') or next((c.get('model') for c in reversed(attempts) if c.get('model')),'not recorded')
  media=v.get('media',{});latency=v.get('vlm_ms',a.get('latency_ms',{}).get('vlm_memory_generation'))
  content=[f'# Clip {e["clip"]} — VLM output','',f'**{e["status"]}** · model `{model}`','',
           '**Source:** '+str(source.get('source','not recorded'))]
  if 'start_seconds_in_source' in source:content.append(f'**Source range:** {source["start_seconds_in_source"]:.3f}–{source["end_seconds_in_source"]:.3f} seconds.')
  content += [f'**VLM time:** {ms(latency)} ms · **sampled video frames:** {media.get("frame_count", "not recorded")} · **parsed memory valid:** {v.get("valid_memory_json", "not recorded")}.','']
  for heading,items in [('Generated episodic descriptions',episodic),('Generated semantic conclusions',semantic)]:
   content += ['## '+heading,'']
   content += ['- '+clean(x) for x in items] if items else ['No validated output was saved for this section.']
   content+=['']
  if any(a.get('override',{}).get('applied',{}).values()):
   content += ['**An override was applied before graph insertion.** The sections above retain the original model output; inspect the audit for effective memory.','']
  content += ['## Exact returned final text','',literal(e['raw_response']) if e['raw_response'] else 'No final response text was captured.','']
  if attempts:
   content += ['## Attempts','', '| Attempt | Call ID | Purpose | Status / finish | Latency ms | Input tokens | Output tokens |','| --- | --- | --- | --- | ---: | ---: | ---: |']
   for n,c in enumerate(attempts,1):
    finish='error' if c.get('error') else c.get('finish_reason','recorded' if c.get('response') else 'no response captured')
    content.append('| '+' | '.join(str(x).replace('|','\\|') for x in [n,c.get('call_id','not recorded'),c.get('purpose','memory'),finish,ms(c.get('latency_ms')),c.get('input_tokens','—'),c.get('output_tokens','—')])+' |')
    if c.get('error'):content+=['',f'Attempt {n} error: '+literal(str(c['error'])),'']
   # Earlier failed/different responses are observable without confusing them with accepted text.
   different=[(n,c) for n,c in enumerate(attempts,1) if c.get('response') and c['response']!=e['raw_response']]
   for n,c in different:content+=['',f'### Other returned output — attempt {n}','',literal(c['response'])]
  prov=provenance/(e['name']+'.json')
  payload={'clip_id':e['clip'],'source':source,'commit_state':e['status'],'generated_memory':memory,'selected_final_text':e['raw_response'],'attempts':attempts,'source_audit':str(e['audit_path']) if e['audit_path'] else None,'source_call_files':[str(p) for p in call_sources]}
  write(prov,json.dumps(payload,ensure_ascii=False,indent=2))
  content += ['', '## Provenance','', '- '+link(prov,destination,'Exact per-clip responses and attempt metadata')]
  if e['audit_path']:content+=['- '+link(e['audit_path'],destination,'Original audit/source record')]
  content+=['','Full backend responses, including any additional raw output, are retained in provenance. No text was substituted for missing output.']
  write(destination/(e['name']+'.md'),'\n'.join(content))
  src=Path(str(source.get('source','unknown'))).name
  index.append(f'| [{e["clip"]}: {model}]({e["name"]}.md) | {src} | {e["status"]} | {len(episodic)} | {len(semantic)} | {ms(latency)} | {len(attempts)} |')
 if not entries:index+=['','No clip-associated VLM output records are available for this diagnostic. See the run’s memories/provenance links; no clip mapping was invented.']
 write(destination/'README.md','\n'.join(index))
 return len(entries)
