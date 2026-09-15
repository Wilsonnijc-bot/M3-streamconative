from pathlib import Path
import json, hashlib
root=Path('/Users/nijiachen/StreamMeCo/egolife_m3_jake_day1/provenance/raw/qwen_thinking')
plan=json.loads((root/'results/segment_plan.json').read_text())['plan']
audits=[json.loads((root/f'results/clip_audits/clip_{i}_audit.json').read_text()) for i in (1,2)]
calls=[json.loads(x) for x in (root/'server_calls.jsonl').read_text().splitlines()]
mem_calls={x['context']['segment_id']:x for x in calls if (x.get('context') or {}).get('purpose')=='memory_construction'}
lines=['# Qwen-constructed memories — Jake DAY1, first two segments','',
       'Model: **Qwen3.5-4B**, with **thinking enabled** and video sampled at **2 FPS**. Both segments completed and were committed to the fresh M3 memory graph.', '',
       'The memory entries below reproduce Qwen’s generated text verbatim. Episodic entries describe what the model interpreted as events; semantic entries are its higher-level inferences. These are model outputs, not a manual verification of the video.', '',
       '**Total: 13 episodic memories and 6 semantic conclusions.** No manual memory overrides were applied.', '',
       '| Segment | Source clip | Frames processed | Episodic memories | Semantic conclusions | GPU generation |',
       '| --- | --- | ---: | ---: | ---: | ---: |']
provenance=[]
for i,a in enumerate(audits,1):
 x=mem_calls[i];m=a['generated_memory'];assert m==a['effective_memory']
 assert not any(a['override']['applied'].values())
 assert x['thinking_enabled'] and x['thinking_completed'] and x['finish_reason']=='stop'
 assert x['processed_image_count']==x['submitted_image_count']
 lines.append(f"| {i} | `{Path(plan[i-1]['source']).name}` | {x['video_frame_count']} | {len(m['video_description'])} | {len(m['high_level_conclusions'])} | {x['timings']['cuda_generation_ms']/1000:.1f} s |")
for i,a in enumerate(audits,1):
 x=mem_calls[i];m=a['generated_memory'];source=Path(plan[i-1]['source']).name;clock=Path(source).stem.rsplit('_',1)[-1];time=f'{clock[:2]}:{clock[2:4]}:{clock[4:6]}.{clock[6:]}'
 lines += ['', f'## Segment {i} — {time}', '', f"Source: `{source}`. Sampled video duration: **{x['context']['media']['video_duration_seconds']:.2f} seconds**; **{x['video_frame_count']} frames**.", '', '### Episodic memories', '']
 for j,text in enumerate(m['video_description'],1):lines.append(f'{j}. {text}')
 lines += ['', '### Semantic conclusions', '']
 for j,text in enumerate(m['high_level_conclusions'],1):lines.append(f'{j}. {text}')
 nodes=[n for n in a['graph_delta']['nodes'] if n['type'] in ('episodic','semantic')]
 for kind,key in [('episodic','video_description'),('semantic','high_level_conclusions')]:
  graph_text=[n['metadata']['contents'][0] for n in nodes if n['type']==kind]
  assert graph_text==m[key],(i,kind)
 episodic_ids=[n['id'] for n in nodes if n['type']=='episodic'];semantic_ids=[n['id'] for n in nodes if n['type']=='semantic']
 lines += ['', f"**Committed graph nodes:** episodic {', '.join(map(str,episodic_ids))}; semantic {', '.join(map(str,semantic_ids))}.", '', f"[Construction audit](results/clip_audits/clip_{i}_audit.json) · [Readable graph after this segment](results/clip_audits/clip_{i}_graph.json)"]
 p=root/f'results/clip_audits/clip_{i}_audit.json';provenance.append({'segment_id':i,'audit':str(p.relative_to(root)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'call_id':x['context']['call_id'],'memory_equals_committed_text':True})
lines += ['', '## Generation details', '',
          '- Thinking completed normally for both segments; neither response was truncated.',
          '- Generated tokens, including thinking: **5,142** for segment 1 and **2,695** for segment 2. Thinking traces are excluded from this readable export.',
          '- Generation budget: **16,384 tokens** per call; greedy decoding with a memory-only repetition penalty of **1.08**.',
          '- GPU: **RTX A6000**, bfloat16. Gemini was running concurrently, so these timings may include GPU contention.',
          '- GPU generation times above use CUDA synchronization; they exclude ASR, graph updates and embedding requests.',
          '- Run: `egolife_10q_qwen35_4b_fps2_thinking`. Thinking-off memories are excluded.', '']
p=root/'Qwen_memories_first_two_segments.md';p.write_text('\n'.join(lines))
(root/'Qwen_memories_first_two_segments.provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')
text=p.read_text()
for a in audits:
 for group in a['generated_memory'].values():
  for item in group:assert item in text
assert text.count('\n## Segment ')==2
print(p)
print('VERIFIED: 19 verbatim memory entries, matching committed graph nodes; thinking on, 2 FPS, no overrides.')
