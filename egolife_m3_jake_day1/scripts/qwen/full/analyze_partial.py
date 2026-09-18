from pathlib import Path
import json,re,statistics,datetime
R=Path(__file__).resolve().parents[3];raw=R/'provenance/raw/qwen_thinking';r=raw/'results';out=R/'results/qwen_thinking'
def read(p):
 rows=[]
 if p.exists():
  for l in p.read_text().splitlines():
   try:rows.append(json.loads(l))
   except json.JSONDecodeError:pass
 return rows
def stats(values):
 return {'n':len(values),'mean':statistics.mean(values),'median':statistics.median(values),'p95':sorted(values)[max(0,__import__('math').ceil(.95*len(values))-1)]} if values else {}
schedule=read(r/'segment_schedule_events.jsonl');committed=[x for x in schedule if x['status']=='committed'];skips=[x for x in schedule if x['status']!='committed']
audits=[]
for row in committed:
 p=r/f"clip_audits/clip_{row['segment_id']}_audit.json"
 if p.exists():audits.append(json.loads(p.read_text()))
identity=[]
for a in audits:
 vlm=a['stage_details']['vlm'];m=a['generated_memory'];expected=set(vlm.get('supplied_voice_ids',[]))
 episodic=set(re.findall(r'<voice_\d+>',' '.join(m['video_description'])))
 all_ids=set(re.findall(r'<voice_\d+>',' '.join(m['video_description']+m['high_level_conclusions'])))
 if expected:identity.append({'segment':a['clip_id'],'expected':len(expected),'episodic':len(expected&episodic),'any':len(expected&all_ids),'complete_episodic':expected<=episodic,'complete_any':expected<=all_ids,'unknown_voice_ids':sorted(all_ids-expected)})
calls=read(r/'qwen_calls.jsonl');memory=[x for x in calls if x.get('purpose')=='memory_construction'];good=[x for x in memory if not x.get('error')]
latest=max(audits,key=lambda a:a['clip_id']);graph=json.loads((r/f"clip_audits/clip_{latest['clip_id']}_graph.json").read_text())
last20=schedule[-20:];interval=(last20[-1]['commit_epoch']-last20[0]['commit_epoch'])/(len(last20)-1)
asr=read(r/'asr_calls.jsonl');asr_counts={k:sum(x.get('status')==k for x in asr) for k in ['cache_hit','success','error']}
latency={k:stats([a['latency_ms'][k]/1000 for a in audits if isinstance(a.get('latency_ms',{}).get(k),(int,float))]) for k in latest['latency_ms']}
vlm=stats([a['stage_details']['vlm']['vlm_ms']/1000 for a in audits]);gpu=stats([x['timings']['cuda_generation_ms']/1000 for x in good if 'timings' in x]);tokens=stats([x['output_tokens'] for x in good if isinstance(x.get('output_tokens'),int)])
episodic=sum(len(a['generated_memory']['video_description']) for a in audits);semantic=sum(len(a['generated_memory']['high_level_conclusions']) for a in audits)
other=R/'provenance/raw/gemini/results/clip_audits';paired=[]
for a in audits:
 p=other/f"clip_{a['clip_id']}_audit.json"
 if p.exists():
  g=json.loads(p.read_text());gms=g.get('stage_details',{}).get('vlm',{}).get('vlm_ms')
  if isinstance(gms,(int,float)):paired.append((a['stage_details']['vlm']['vlm_ms']/1000,gms/1000))
snapshots=[]
for p in sorted((r/'memory').glob('q*_uncompressed/metadata.json')):
 d=json.loads(p.read_text());last=max(x['absolute_end_seconds'] for x in d['source_segments']);snapshots.append({'snapshot':p.parent.name,'latest_source_end':last,'query_time':d['query_time_seconds'],'within_cutoff':last<=d['query_time_seconds']+1e-6})
assert all(x['within_cutoff'] for x in snapshots)
errors=read(r/'api_failures.jsonl');qa=sum(len(read(p)) for p in r.glob('method_*.jsonl'))
result={'as_of':datetime.datetime.now(datetime.timezone.utc).isoformat(),'processed':len(schedule),'committed':len(committed),'skipped':[x['segment_id'] for x in skips],'snapshots':len(list((r/'memory').glob('q*_uncompressed'))),'qa_rows':qa,'vlm_seconds':vlm,'gpu_generation_seconds':gpu,'generated_tokens':tokens,'recent_seconds_per_segment':interval,'remaining_construction_minutes_estimate':(144-len(schedule))*interval/60,'generated_episodic':episodic,'generated_semantic':semantic,'graph_counts':latest['counts'],'graph_edges':len(graph.get('edges',[])),'face_identity_clips':sum(a['counts'].get('face_identities',0)>0 for a in audits),'snapshot_cutoff_checks':snapshots,'identity':{'segments_with_voice_input':len(identity),'fully_attributed_episodic':sum(x['complete_episodic'] for x in identity),'fully_attributed_any_memory':sum(x['complete_any'] for x in identity),'provided_ids':sum(x['expected'] for x in identity),'ids_in_episodic':sum(x['episodic'] for x in identity),'ids_in_any_memory':sum(x['any'] for x in identity),'segments_with_noninput_voice_ids':[x['segment'] for x in identity if x['unknown_voice_ids']]},'asr_attempt_statuses':asr_counts,'latency_stage_seconds':latency,'paired_vlm':{'n':len(paired),'qwen_median_seconds':statistics.median(x[0] for x in paired) if paired else None,'gemini_median_seconds':statistics.median(x[1] for x in paired) if paired else None},'failure_records':errors}
(raw/'construction_analysis.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
i=result['identity']
lines=['# Qwen full benchmark — interim analysis','',f"Fetched and analyzed: {result['as_of']}",'', '**This is an interim construction analysis, not a completed QA benchmark.**','',
 f"Processed **{len(schedule)}/144 segments**: **{len(committed)} committed**, **{len(skips)} skipped**. Saved **{result['snapshots']}/10 query snapshots** and **{qa}/40 predictions**.",'',
 '## Construction speed','',f"Successful committed memory calls: median **{vlm['median']:.1f} s**, mean **{vlm['mean']:.1f} s**, P95 **{vlm['p95']:.1f} s** (client wall time).",'',
 f"Successful non-error model calls: median CUDA generation **{gpu['median']:.1f} s**; median generated tokens including thinking **{tokens['median']:,.0f}**.",'',
 f"The latest 20 processed segments averaged **{interval:.1f} s per commit interval**. At that observed pace, the remaining {144-len(schedule)} segments would take roughly **{result['remaining_construction_minutes_estimate']:.0f} minutes**, excluding compression, adaptation, QA evaluation and interruptions.",'',
 'These are separate timing scopes, not additive stages. Thinking remains on; FPS remains 2. Concurrent GPU execution was authorized, and the server restarted after the short-audio decoder fix. Provider cache hits are not fresh service inference measurements.','',
 '## Memory and identity quality','',f"The committed clips generated **{episodic} episodic descriptions** and **{semantic} semantic conclusions** before graph integration. The latest graph has **{len(graph['nodes'])} nodes** and **{len(graph.get('edges',[]))} edges**.",'',
 f"Of **{i['segments_with_voice_input']} clips with supplied voice IDs**, **{i['fully_attributed_episodic']}** mention every supplied voice ID in episodic memory; **{i['fully_attributed_any_memory']}** mention every supplied ID somewhere in episodic or semantic memory.",'',
 f"Across per-clip speaker-ID occurrences, **{i['ids_in_episodic']}/{i['provided_ids']}** are retained in episodic memory and **{i['ids_in_any_memory']}/{i['provided_ids']}** in either memory class.",'',
 'This is a direct-reference coverage check, not a correctness score: a voice can be mentioned with an incorrect claim, and absence does not prove every omitted utterance was relevant. The earlier manual test found ASR provider-label/person confusion and transcript mistranslation. The full run therefore should not be treated as having solved speaker grounding merely because graphs commit successfully.','',
 f"Preprocessing supplied face identities in {result['face_identity_clips']} committed clips. The latest graph contains {sum(n['type']=='voice' for n in graph['nodes'])} voice-identity nodes; these do not establish an equal number of distinct people. Face-to-voice grounding cannot be established where qualified face identities are absent.",'',
 '## Failures and coverage','']
for x in errors:
 if 'segment_id' in x:lines.append(f"- Segment **{x['segment_id']}**: {x.get('error','unavailable')}")
lines+=['','Segments 98 and 122 also had degraded ASR: MAI exhausted its two attempts (HTTP 503 and 429 respectively), while Deepgram remained available. These were committed with partial ASR rather than skipped. Saved snapshot metadata records pass the source-timestamp cutoff check (see exact counts and boundaries in the analysis data).','',
 'The failed segments were rolled back and skipped; downstream methods share the resulting coverage gaps. The later segment-98 MoviePy error was repaired and resumed rather than counted as an additional missing segment.','',
 '## Retrieval and accuracy','',
 'No QA results are available yet. Accuracy, A/B/C/D retrieval latency, and the effect of Mandol’s larger pool cannot be assessed at this stage. Mandol Method D is configured for **100 candidates and 20 final results**; this differs from the original smaller pool, so subsequent method comparisons must state that difference.','']
if paired:lines+=['## Available Gemini timing context','',f"Across {len(paired)} matching segment IDs with saved VLM timings, median Qwen client time is **{statistics.median(x[0] for x in paired):.1f} s**, versus **{statistics.median(x[1] for x in paired):.1f} s** for Gemini.",'','This is descriptive, not a controlled causal comparison: backend, thinking behavior, Qwen-specific prompt, service execution and contention differ. It says nothing yet about answer accuracy.','']
lines+=['[Live status](README.md) · [Per-clip outputs](vlm_outputs/README.md) · [Committed memories](memories.md) · [Detailed latency](latency.md) · [Exact analysis data](../../provenance/raw/qwen_thinking/construction_analysis.json)','']
(out/'analysis.md').write_text('\n'.join(lines));print(json.dumps({k:v for k,v in result.items() if k not in ['failure_records','latency_stage_seconds']},indent=2))
