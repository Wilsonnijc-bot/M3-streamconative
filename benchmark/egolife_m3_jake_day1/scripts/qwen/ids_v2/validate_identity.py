import os,json,re
from pathlib import Path
r=Path(os.environ['QWEN_RUN']);rows=[];problems=[]
commits={x['segment_id']:x['status'] for x in [json.loads(l) for l in (r/'results/segment_schedule_events.jsonl').read_text().splitlines()]}
for i in (1,2):
 p=r/f'results/clip_audits/clip_{i}_audit.json'
 if not p.exists():problems.append(f'segment {i}: no successful audit');continue
 a=json.loads(p.read_text());v=a['stage_details']['vlm'];m=a['effective_memory'];expected=set(v['supplied_voice_ids'])
 episodic=set(re.findall(r'<voice_\d+>',' '.join(m['video_description'])))
 all_text=' '.join(m['video_description']+m['high_level_conclusions']);used=set(re.findall(r'<voice_\d+>',all_text))
 g=json.loads((r/f'results/clip_audits/clip_{i}_graph.json').read_text())
 voice_edges=[e for e in a['graph_delta']['edges'] if e.get('source_type')=='voice' or e.get('target_type')=='voice']
 # Graph delta edges may omit type labels; resolve endpoints against the saved graph.
 nodes={n['id']:n for n in g['nodes']}
 new_ids={n['id'] for n in a['graph_delta']['nodes']}
 voice_edges=[e for e in g['edges'] if (e['source'] in new_ids or e['target'] in new_ids) and ('voice' in (e['source_type'],e['target_type']))]
 call=v['attempts'][0]
 issues=[]
 if commits.get(i)!='committed':issues.append('not committed')
 if expected-episodic:issues.append('missing episodic speaker references: '+str(sorted(expected-episodic)))
 if used-expected:issues.append('invented voice IDs: '+str(sorted(used-expected)))
 if a['counts']['face_identities']==0 and re.search(r'<face_\d+>',all_text):issues.append('invented face IDs')
 if not call['thinking_enabled'] or not call['thinking_completed'] or call['finish_reason']!='stop':issues.append('thinking incomplete or truncated')
 if call['vlm_fps']!=2 or call['processed_image_count']!=call['submitted_image_count']:issues.append('FPS/frame mismatch')
 if expected and not voice_edges:issues.append('no new speaker-memory graph edges')
 row={'segment_id':i,'supplied_voice_ids':sorted(expected),'episodic_voice_ids':sorted(episodic),'new_voice_memory_edges':len(voice_edges),'frames':call['video_frame_count'],'thinking_completed':call['thinking_completed'],'generation_seconds':call['timings']['cuda_generation_ms']/1000,'output_tokens':call['output_tokens'],'memory':m,'problems':issues}
 rows.append(row);problems.extend(f'segment {i}: {x}' for x in issues)
result={'status':'passed' if not problems and len(rows)==2 else 'failed','scope':'two-segment identity-reference and graph-link test; transcript fidelity also requires review','rows':rows,'problems':problems}
(r/'results/identity_validation.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
print(json.dumps(result,ensure_ascii=False),flush=True)
if result['status']!='passed':raise RuntimeError('Identity validation failed')
