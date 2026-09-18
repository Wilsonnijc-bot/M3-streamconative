"""Render raw experiment artifacts as a stable, human-readable Markdown contract."""
from pathlib import Path
import json,re,os,hashlib,datetime,statistics,fcntl,sys
from render_vlm_outputs import render as render_vlm_outputs
from analyze_gemini_latency import build_analysis
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT.parent/'StreamMeCo/mmagent'))
from videograph_markdown import load_graph, render_graph, render_character_dictionary
RAW=ROOT/'provenance/raw';OUT=ROOT/'results'
TITLES={'gemini':'Gemini — first ten questions','qwen_non_thinking':'Qwen3.5 4B — non-thinking','qwen_thinking':'Qwen3.5 4B thinking + identity prompt — first ten questions','qwen_thinking_baseline':'Qwen3.5 4B thinking — baseline prompt preflight','qwen_identity_v2':'Qwen3.5 4B — identity prompt v2','gemini_preflight':'Gemini — three-clip preflight (cold retrieval)','first_clip_hyperstack':'First-clip model comparison — Hyperstack','first_clip_openrouter':'First-clip model comparison — OpenRouter','gemini_request':'Early Gemini request/response','legacy_smoke':'Early memory/QA smoke test'}
SMOKE_CASES=set(TITLES)-{'gemini','qwen_thinking'}
NOW=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')

def read(p,default=None):
 try:return json.loads(p.read_text())
 except (OSError,json.JSONDecodeError):return default

def lines(p):
 if not p.exists():return []
 result=[]
 for s in p.read_text(errors='replace').splitlines():
  try:result.append(json.loads(s))
  except json.JSONDecodeError:pass
 return result

def write(p,text):
 p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_suffix('.md.tmp');tmp.write_text(text.rstrip()+'\n');tmp.replace(p)

def link(p,from_dir,label=None):return '['+(label or p.name)+']('+os.path.relpath(p,from_dir)+')'
def cell(v):
 if v is None:return '—'
 if isinstance(v,float):return f'{v:,.2f}'
 return str(v).replace('|','\\|').replace('\n','<br>')
def table(cols,rows):return '\n'.join(['| '+' | '.join(cols)+' |','| '+' | '.join(['---']*len(cols))+' |']+['| '+' | '.join(cell(x) for x in row)+' |' for row in rows])
def number(p):
 m=re.search(r'(?:clip_|q)(\d+)',p.name);return int(m.group(1)) if m else 0

def status(raw,root,qa_count):
 validation=read(root/'validation.json',{})
 if validation.get('status')=='complete' and validation.get('qa_rows')==40:return 'Complete: 40 verified QA predictions'
 path=raw/'pipeline_status.txt'
 if not path.exists():path=raw/'launcher_status.txt'
 text=path.read_text() if path.exists() else ''
 if 'exit_status=running' in text:return 'Running'
 if 'exit_status=optimizing' in text or 'exit_status=repairing' in text:return 'Running setup/recovery'
 if re.search(r'exit_status=[1-9]',text):return 'Stopped after failure; incomplete benchmark'
 if 'exit_status=0' in text:return 'Stage/preflight exited successfully; full benchmark not verified'
 return 'Saved diagnostic/preflight artifacts; full benchmark not verified'

def graph_markdown(g,title,source=None,output=None):
 if not isinstance(g,dict) or not isinstance(g.get('nodes'),list):return [f'## {title}','','No readable graph is available.','']
 return render_graph(g,title,level=2,source=source,output=output)

def saved_graph(path):
 """Prefer original state; reduced JSON cannot expose character mappings/indexes."""
 candidates=[path.with_suffix('.pkl')]
 try:candidates.insert(0,ROOT/'cache/graphs'/path.relative_to(RAW).with_suffix('.pkl'))
 except ValueError:pass
 for candidate in candidates:
  if candidate.is_file():return load_graph(candidate),candidate
 return read(path),path

def render_case(raw,memory_only=False):
 case=raw.name;out=(ROOT/'smoke_tests' if case in SMOKE_CASES else OUT)/case;out.mkdir(parents=True,exist_ok=True)
 root=raw/'results' if (raw/'results').exists() else raw
 selected_d=read(root/'method_D_selection.json',{})
 d_note=('**Method D:** up to **100 candidates → 20 final evidence nodes**, Qwen embedding and reranking via **302.ai**. These are the later rerun measurements; A/B/C retain their original measurements. The earlier two-node D result is retained only in provenance.' if selected_d else '')
 audits=[read(p) for p in sorted((root/'clip_audits').glob('*_audit.json'),key=number)];audits=[a for a in audits if a]
 schedule=lines(root/'segment_schedule_events.jsonl')
 committed={int(x.get('segment_id',x.get('clip_id',0))) for x in schedule if x.get('status')=='committed'}
 for p in raw.glob('*.log'):
  committed.update(map(int,re.findall(r'SEGMENT_COMPLETE id=(\d+)',p.read_text(errors='replace'))))
 if committed:audits=[a for a in audits if a['clip_id'] in committed]
 latest=max((a['clip_id'] for a in audits),default=0)
 snapshot_dirs=sorted((root/'memory').glob('q*_uncompressed'))
 qa=[]
 for p in sorted(root.glob('method_*.jsonl')):qa+=lines(p)
 if case=='gemini_preflight':
  qa=[]
  for p in sorted((raw/'provenance').glob('method_*.jsonl')):
   if 'initial_timing' not in p.name:qa+=lines(p)
 state=status(raw,root,len(qa))
 if case not in SMOKE_CASES and state.startswith('Stage/preflight'):state='Not running; full benchmark incomplete'
 manifest=read(root/'model_manifest.json',read(raw/'provenance/model_manifest.json',{})) or {}
 title=TITLES.get(case,case)
 model=manifest.get('reasoning_model',manifest.get('model','See provenance'))
 m=['# '+title+' — memories','',f'Updated: {NOW}. Status: **{state}**.','',
    'Nodes and their connections. Inferences are model-generated, not verified facts.','']
 if snapshot_dirs:
  latest_query=snapshot_dirs[-1].name.split('_')[0]
  m+=[link(out/'snapshots'/f'{latest_query}.md',out,'Query-time character mappings')+' · '
      +link(ROOT.parent/'StreamMeCo/mmagent/videograph_markdown.md',out,'Exporter usage')+'.','']
  query_graph,query_source=saved_graph(snapshot_dirs[-1]/'graph.json')
  if query_graph:
   m+=render_character_dictionary(query_graph,query_source,out/'memories.md',latest_query)
 if latest:
  g,source=saved_graph(root/'clip_audits'/f'clip_{latest}_graph.json')
  m+=graph_markdown(g,f'Latest committed memory — segment {latest}',source,out/'memories.md')
 elif case=='gemini_preflight':
  for name in ['uncompressed','compressed']:m+=graph_markdown(read(raw/'constructed_memory'/name/'graph.json'),name.title()+' preflight memory')
 elif case=='legacy_smoke':
  data=read(raw/'memory/raw/memory_smoke.json',{})
  m+=['## Saved smoke observation','','This early output was truncated; it is not a complete memory graph.','']+['- '+str(o.get('content','')) for o in data.get('observations',[])]+['']
 elif case=='gemini_request':
  data=read(raw/'response.json',{});content=(data.get('choices') or [{}])[0].get('message',{}).get('content','')
  m+=['## Raw Gemini-generated memory','','This diagnostic has a saved response but no committed graph.','']
  try:parsed=json.loads(re.sub(r'^```(?:json)?\s*|\s*```$','',content.strip()))
  except json.JSONDecodeError:parsed={}
  for key in ['video_description','video_descriptions','high_level_conclusions']:
   if parsed.get(key):m+=['### '+key.replace('_',' ').title(),'']+['- '+str(v) for v in parsed[key]]+['']
  if not parsed:m+=[content,'']
 elif case.startswith('first_clip_'):
  for p in sorted(raw.glob('*.json')):
   x=read(p,{})
   if isinstance(x,dict) and x.get('graph'):m+=graph_markdown(x['graph'],x.get('model',p.stem))
 else:m+=['No committed graph artifact is available for this diagnostic. See '+link(raw,out,'raw records')+'.','']
 if snapshot_dirs:
  m+=['## Query-time snapshots','','Each snapshot includes only its own chronological coverage.','']
  for d in snapshot_dirs:
   g,source=saved_graph(d/'graph.json');md=read(d/'metadata.json',{})
   if not g:continue
   name=d.name.split('_')[0]+'.md'
   content=['# '+d.name+' — memory snapshot','',f'Question timestamp: {md.get("question",{}).get("query_time", "see metadata")}. Skipped segments: {len(md.get("skipped_segments",[]))}; ASR-degraded segments: {len(md.get("asr_degraded_segments",[]))}.','']+graph_markdown(g,'Saved graph',source,out/'snapshots'/name)
   write(out/'snapshots'/name,'\n'.join(content));m.append('- '+link(out/'snapshots'/name,out))
 for d in sorted((root/'streammeco_compressed').glob('q*')):
  graph=read(d/'graph.json')
  if graph:
   name=d.name+'_compressed.md'
   write(out/'snapshots'/name,'\n'.join(['# '+d.name+' — compressed memory','']+graph_markdown(graph,'Compressed graph')))
   m+=['- '+link(out/'snapshots'/name,out,'Compressed '+d.name)]
 write(out/'memories.md','\n'.join(m))
 if memory_only:return

 latency=['# '+title+' — latency','',f'Updated: {NOW}. **{state}**.','']
 if d_note:latency += [d_note,'']
 if case=='gemini':latency+=build_analysis(root)
 latency+=['All values below are measured milliseconds unless stated otherwise. Empty fields mean unavailable, not zero. Overlapping stages must not be added as end-to-end latency. Cached acquisition, warmup, retries and execution-policy changes remain separate.','']
 context=read(root/'measurement_context.json',{})
 if context.get('note'):latency+=['**Measurement context:** '+context['note'],'']
 if manifest.get('execution_policy'):latency+=['Execution policy: **'+str(manifest['execution_policy'])+'**.','']
 if audits:
  sched={int(x.get('segment_id',0)):x for x in schedule}
  latency+=['## Memory construction','',table(['Segment','Nodes','Decode','ASR stage','Reasoning','Text embedding','Ready queue','Ordered processing','Admission → checkpoint'],[
   [a['clip_id'],a.get('counts',{}).get('nodes_after_clip'),a['latency_ms'].get('clip_decode'),a['latency_ms'].get('asr_total'),a['latency_ms'].get('vlm_memory_generation'),a['latency_ms'].get('text_embedding'),sched.get(a['clip_id'],{}).get('ready_to_ordered_ms'),a.get('ordered_processing_ms'),sched.get(a['clip_id'],{}).get('segment_latency_ms')] for a in audits]),'',
   'The two latency columns on the right are unavailable for older serial records. Their original `end_to_end_memory_generation_ms` values remain in the raw audit; they are not silently mixed with pipeline admission-to-checkpoint measurements.','',
   '## Preprocessing and graph-update detail','',table(['Segment','Deepgram','MAI','Speech embedding','Face detection','Face clustering','Graph update','ASR cache/precompute'],[
   [a['clip_id'],a['latency_ms'].get('deepgram_asr'),a['latency_ms'].get('mai_transcribe_asr'),a['latency_ms'].get('speech_embedding_campplus'),a['latency_ms'].get('facial_detection_recognition_buffalo_l'),a['latency_ms'].get('face_clustering'),a['latency_ms'].get('graph_update_total'),str(a.get('stage_details',{}).get('voice',{}).get('cache_hit',False))+'/'+str(a.get('stage_details',{}).get('voice',{}).get('asr_precomputed',False))] for a in audits]),'',
   'ASR provider times can overlap; the ASR-stage column above is independently measured wall time. An ASR cache hit is not a new provider-speed measurement.','']
  batches=[]
  for a in audits:
   b=a.get('stage_details',{}).get('text_embedding_batch')
   if b:batches.append([a['clip_id'],b.get('input_count'),b.get('latency_ms'),b.get('total_tokens'),len(b.get('calls',[]))])
  if batches:latency+=['## Per-clip embedding batches','',table(['Segment','Texts','Whole batch ms','Tokens','API attempts'],batches),'','Each input retains its own vector. Individual-text latency is unavailable; batch time is not divided by text count.','']
  policies=lines(root/'execution_policies.jsonl')
  if policies:latency+=['## Timing-policy boundaries','',table(['First segment','ASR','HTTP','Embedding','Lookahead'],[[x.get('first_segment'),x.get('asr'),x.get('http'),x.get('memory_embeddings'),x.get('prefetch_ahead')] for x in policies]),'']
 elif case=='gemini_preflight':
  old=raw/'LATENCY.md'
  if old.exists():
   text=old.read_text();text=re.sub(r'\]\(([^)]+)\)',lambda z:']('+os.path.relpath(raw/z.group(1),out)+')' if not z.group(1).startswith(('http','#')) else z.group(0),text)
   latency+=['## Original selected cold-start preflight','','This is historical cold-start data, not the upcoming warm-query benchmark.','',text]
 elif case.startswith('first_clip_'):
  samples=[read(p,{}) for p in raw.glob('*.json')];samples=[x for x in samples if isinstance(x,dict) and 'vlm_ms' in x]
  latency+=['## First-clip construction comparison','',table(['Model','Total construction','VLM','Text embedding','Graph update'],[[x.get('model'),x.get('end_to_end_memory_generation_ms'),x.get('vlm_ms'),x.get('text_embedding_ms'),x.get('graph_update_ms')] for x in samples]),'']
 if qa:
  latency+=['## QA measurements','',table(['Q','Method','Mode','Retrieval requests','Reasoning calls','Retrieval total','Reasoning total','Question → answer','Answer','Correct'],[
   [x['question_index'],x['method'],x.get('latency_mode','historical preflight / cold'),x['retrieval_round_count'],len(x.get('controller_calls',[])) or 1,sum(e['retrieval']['TOTAL_RETRIEVAL_MS'] for e in x['retrieval_rounds']),sum(c['latency_ms'] for c in x['controller_calls']) if x.get('controller_calls') else x['final_answer_model_ms'],x['FULL_QUESTION_TO_ANSWER_MS'],x['prediction'],x['correct']] for x in qa]),'',
   '### Retrieval-stage detail','',table(['Q/method/round','Embedding','Dense','Sparse','StreamMeCo scoring','Fusion','Lookup','Rerank','Total'],[
   [f'{x["question_index"]}/{x["method"]}/{i}',e.get('embedding_ms',e.get('embedding',{}).get('total_ms')),e['retrieval'].get('dense_ms'),e['retrieval'].get('sparse_ms'),e.get('streammeco_tmr_scoring_ms',e['retrieval'].get('StreamMeCo/TMR_ms')),e['retrieval'].get('fusion_ms'),e['retrieval'].get('memory_unit_lookup_ms',e.get('graph_node_selection_ms')),e['retrieval'].get('rerank_ms'),e['retrieval']['TOTAL_RETRIEVAL_MS']] for x in qa for i,e in enumerate(x['retrieval_rounds'],1)]),'']
  latency+=['### Reasoning calls','',table(['Q/method/call','Purpose','Latency','Input tokens','Output tokens'],[
   [f'{x["question_index"]}/{x["method"]}/{i}',c.get('purpose'),c.get('latency_ms'),c.get('input_tokens'),c.get('output_tokens')] for x in qa for i,c in enumerate(x.get('controller_calls') or [x['final_answer_call']],1)]),'']
  aggregates=read(root/'aggregate_metrics.json',{})
  if aggregates:
   latency+=['### Per-method aggregates','',table(['Method','Correct / N','Mean retrieval','Median retrieval','P95 retrieval','Mean QA','Median QA','Mean embedding','Mean model calls'],[[k,f'{v.get("correct")} / {v.get("questions")}',v.get('mean_retrieval_ms'),v.get('median_retrieval_ms'),v.get('p95_retrieval_ms'),v.get('mean_end_to_end_ms'),v.get('median_end_to_end_ms'),v.get('mean_embedding_ms'),v.get('mean_gemini_calls')] for k,v in aggregates.items()]),'']
 else:latency+=['## QA measurements','','No actual A/B/C/D evaluation rows are available for this run yet. Startup or preflight completion is not a completed 40-trial benchmark.','']
 warmups=lines(root/'retrieval_warmup.jsonl')
 if warmups:latency+=['## Excluded setup / warmup','',table(['Q','Method','Snapshot load','Warmup','Status'],[[w.get('snapshot_index'),w.get('method'),w.get('snapshot_load_ms'),w.get('warmup_ms'),w.get('status')] for w in warmups]),'','These are excluded from timed QA calls and warm retrieval latency.','']
 asr=lines(root/'asr_calls.jsonl');failures=lines(root/'api_failures.jsonl')
 if asr:latency+=['## ASR outcomes','',table(['Provider','Successful API attempts','Failed attempts','Cache hits'],[[p,sum(e.get('status')=='success' for e in asr if e.get('provider')==p),sum(e.get('status')=='error' for e in asr if e.get('provider')==p),sum(e.get('status')=='cache_hit' for e in asr if e.get('provider')==p)] for p in sorted({e.get('provider','unknown') for e in asr})]),'']
 if failures:latency+=['## Failed or degraded processing','',table(['Segment/cache','Status','Error'],[[e.get('segment_id',e.get('clip_cache')),e.get('status'),e.get('error',e.get('errors'))] for e in failures]),'']
 latency+=['## Definitions and exact evidence','', '- '+link(ROOT/'scripts/gemini/MEASUREMENT.md',out,'Latency measurement contract'),'- '+link(raw,out,'Raw artifacts and logs'),'',
 'Warm retrieval excludes snapshot/model/index loading and the unrelated startup probe. It includes the actual question embedding, searches, fusion, lookup and reranking. Warmup is recorded separately, and never primes the benchmark question. Provider-internal model residency cannot be controlled.']
 write(out/'latency.md','\n'.join(latency))

 retrieval=['# '+title+' — retrieved memories','']
 if d_note:retrieval += [d_note,'']
 if not qa:retrieval+=['No actual QA retrieval results are available yet. This file will be populated by the next sync after evaluation produces predictions.']
 for x in qa:
  retrieval += [f'## Q{x["question_index"]} · Method {x["method"]}','',x.get('question',{}).get('question',''),'',f'Answer: **{x["prediction"]}**; reference: **{x.get("gold_answer")}**. Retrieval requests: {x["retrieval_round_count"]}.','']
  for i,e in enumerate(x['retrieval_rounds'],1):
   retrieval += [f'### Retrieval {i}', '', '**Query:** '+str(e.get('query_text',x.get('retrieval_query',''))),'']
   for n in e.get('evidence',[]):
    retrieval.append('- **Node '+str(n.get('node_id'))+'**'+(' → M3 '+str(n['m3_node_id']) if 'm3_node_id' in n else '')+': '+' '.join(str(v) for v in n.get('contents',[])))
   retrieval+=['']
 write(out/'retrieval.md','\n'.join(retrieval))
 vlm_count=render_vlm_outputs(raw,out,case,set(committed))
 desc=[f'# {title}','',f'**{state}** · updated {NOW}','',f'Model: `{model}`. Saved committed segment audits: **{len(audits)}**; latest segment: **{latest or "—"}**; query snapshots: **{len(snapshot_dirs)}/10**; actual QA rows: **{len(qa)}/40**.','',
       '- [Per-clip VLM outputs](vlm_outputs/README.md) — generated descriptions, exact final text and all recorded attempts.',
       '- [Memories](memories.md) — compact nodes, connections, and character mappings.',
       '- '+link(ROOT.parent/'StreamMeCo/mmagent/videograph_markdown.md',out,'Reusable graph-to-Markdown exporter')+'.',
       '- [Latency](latency.md) — construction, preprocessing, batch, queue and retrieval stages.',
       '- [Retrieved memories](retrieval.md) — actual questions, rounds and evidence.',
       '- '+link(raw,out,'Raw provenance')+' · '+link(ROOT/'scripts/runs'/case,out,'Run scripts') if (ROOT/'scripts/runs'/case).exists() else '- '+link(raw,out,'Raw provenance')]
 if case=='gemini' and (out/'replays/README.md').exists():
  desc+=['', '- [Memory replays at 20, 40 and 60 minutes](replays/README.md).']
 if case=='qwen_thinking':
  qa_mode=read(root/'model_manifest.json',{}).get('generation',{}).get('qa_thinking',True)
  desc+=['', '**Configuration:** memory construction thinking enabled; QA thinking '+('enabled' if qa_mode else '**disabled (user-requested QA restart)**')+'; 2 FPS VLM sampling; Qwen-only identity prompt v2; 16,384-token output budget. Gemini may share the GPU, so latency can include contention.', '',
         link(raw/'qwen_identity_system_prompt.md',out,'Exact Qwen-specific prompt')+' · '+link(raw/'memory_resume_manifest.json',out,'Memory lineage and known attribution limitations')+' · '+link(raw/'gemini_prompt_unchanged.txt',out,'Gemini prompt hash verification')]
 if case=='qwen_thinking' and (root/'mandol_retrieval_config.json').exists():
  cfg=read(root/'mandol_retrieval_config.json',{})
  desc+=['',f"**Mandol Method D:** candidate pool **{cfg.get('candidate_pool')}**, final results **{cfg.get('final_results')}**. "+link(root/'mandol_retrieval_config.json',out,'Effective retrieval configuration')]
 if (out/'analysis.md').exists():desc+=['','[Interim analysis](analysis.md) — dated interpretation of fetched evidence; see live counts above for newer progress.']
 if case=='gemini_preflight':desc+=['','This is the three-clip functional preflight, not the full first-ten benchmark.']
 if d_note:desc += ['',d_note]
 write(out/'README.md','\n'.join(desc))
 return [link(out/'README.md',ROOT,title),state,latest or '—',len(snapshot_dirs),len(qa)]

def main():
 OUT.mkdir(exist_ok=True);(ROOT/'smoke_tests').mkdir(exist_ok=True);rows=[];smoke_rows=[]
 order=['gemini','gemini_preflight','qwen_non_thinking','qwen_thinking','qwen_identity_v2','first_clip_hyperstack','first_clip_openrouter','gemini_request','legacy_smoke']
 for raw in sorted(RAW.iterdir(),key=lambda p:order.index(p.name) if p.name in order else 99):
  if raw.is_dir():
   row=render_case(raw)
   (smoke_rows if raw.name in SMOKE_CASES else rows).append(row)
 text=['# Jake DAY1 experiments','',f'Updated: {NOW}. Start with a run below; memories and detailed latency are Markdown.','',table(['Full benchmark','State','Latest segment','Snapshots','QA rows'],rows),'','[Smoke tests: first-clip comparisons, preflights and short Qwen checks](smoke_tests/README.md). These are separate from the full 10-question runs.','',
 '## Result contract','','[Read the result contract](RESULT_CONTRACT.md).','', '```text','scripts/                    runners, sync/export tools, handoffs','cache/','  asr/                      provider transcripts, namespaced by run','  faces/                    face detections/features','  voices/                   speaker features and segmented audio','  media/                    prepared/cropped media','  graphs/                   intermediate binary graph caches','  dependencies/             downloaded test/runtime dependencies','results/<run>/','  README.md                 status and entry point','  vlm_outputs/clip_NNNN.md   per-clip model output and attempt history','  memories.md               latest graph as readable text','  snapshots/q01.md ...      exact query-time memory views','  latency.md                detailed timing with scope definitions','  retrieval.md              actual retrieved memories per question/round','smoke_tests/<test>/         first-clip comparisons, preflights and short checks','provenance/                 exact JSON, checkpoints, manifests and logs','```','',
 'Original videos remain outside this result folder; small QA reference files are under provenance/reference_data. No model weights or remote experiment paths were moved. The remote process continues using its existing checkpoint locations. Different Qwen configurations stay separate; they are not merged into one result. Existing cold-start preflight measurements stay labeled separately from warm-query evaluations.','',
 '## Refresh','', '```bash','python3 scripts/sync_run.py gemini','```','',
 'Run that command from this folder, or use its absolute path. The Gemini transfer watcher also updates this layout. Caches are reusable only when provider/model, audio, sampling and schema match; never reuse graph-assigned IDs across different memory constructions.','',
 '- '+link(ROOT/'provenance/relocations.json',ROOT,'Old → new path mapping'),'- '+link(ROOT/'scripts/gemini/MEASUREMENT.md',ROOT,'Latency measurement definitions')]
 write(ROOT/'README.md','\n'.join(text))
 smoke_text=['# Smoke tests','','These are short functional/diagnostic checks. They are not completed 10-question × 4-method benchmarks.','',table(['Smoke test','State','Latest segment','Snapshots','QA rows'],smoke_rows)]
 rendered='\n'.join(smoke_text)
 rendered=re.sub(r'\]\(([^)]+)\)',lambda m:'](../'+m.group(1)+')',rendered)
 write(ROOT/'smoke_tests/README.md',rendered)
 print('RENDERED',len(rows),'benchmarks and',len(smoke_rows),'smoke tests',flush=True)
if __name__=='__main__':
 with (ROOT/'provenance/.render.lock').open('w') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX)
  main()
