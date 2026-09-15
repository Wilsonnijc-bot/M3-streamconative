import json,re,hashlib
from pathlib import Path
root=Path('/Users/nijiachen/StreamMeCo/egolife_m3_jake_day1/provenance/raw/qwen_identity_v2')
validation=json.loads((root/'results/identity_validation.json').read_text())
plan=json.loads((root/'results/segment_plan.json').read_text())['plan']
audits=[json.loads((root/f'results/clip_audits/clip_{i}_audit.json').read_text()) for i in (1,2)]
memories=[a['effective_memory'] for a in audits]
episodic=sum(len(m['video_description']) for m in memories);semantic=sum(len(m['high_level_conclusions']) for m in memories)
lines=['# Qwen memories — speaker-identity prompt refinement','',
       '**Jake DAY1 · first two segments · Qwen3.5-4B · thinking on · 2 FPS**','',
       'These are the model-generated memories committed to a fresh M3 graph. The wording is preserved; speaker IDs are displayed as inline code for readability. No IDs were inserted into the generated memories by postprocessing.','',
       f'**{episodic} episodic memories and {semantic} semantic conclusions.** Identity-reference validation: **{validation["status"]}**.','',
       '| Segment | Supplied voice IDs | IDs retained in episodic memory | New speaker-memory edges | Frames | Generation |',
       '| --- | --- | --- | ---: | ---: | ---: |']
for row in validation['rows']:
 fmt=lambda values:', '.join('`'+v+'`' for v in values)
 lines.append(f"| {row['segment_id']} | {fmt(row['supplied_voice_ids'])} | {fmt(row['episodic_voice_ids'])} | {row['new_voice_memory_edges']} | {row['frames']} | {row['generation_seconds']:.1f} s |")
provenance=[]
for i,(a,m) in enumerate(zip(audits,memories),1):
 assert a['generated_memory']==m and not any(a['override']['applied'].values())
 lines += ['',f'## Segment {i}','',f"Source: `{Path(plan[i-1]['source']).name}`.",'','### Episodic memories','']
 for j,text in enumerate(m['video_description'],1):lines.append(f"{j}. "+re.sub(r'<(?:voice|face)_\d+>',lambda match:'`'+match[0]+'`',text))
 lines += ['','### Semantic conclusions','']
 for j,text in enumerate(m['high_level_conclusions'],1):lines.append(f"{j}. "+re.sub(r'<(?:voice|face)_\d+>',lambda match:'`'+match[0]+'`',text))
 lines += ['',f'[Construction audit](results/clip_audits/clip_{i}_audit.json) · [Committed graph](results/clip_audits/clip_{i}_graph.json)']
 p=root/f'results/clip_audits/clip_{i}_audit.json';provenance.append({'segment_id':i,'source_audit':str(p.relative_to(root)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
lines += ['','## What changed','',
          'Only the isolated Qwen memory path received an additional system message: retain supplied speaker IDs, summarize each speaker’s actual transcript, and avoid guessing voice-to-face identities. The shared base prompt and Gemini memory prompt were left unchanged. Thinking, 2-FPS sampling, the 16,384-token budget and decoding settings were retained.', '',
          '[Exact Qwen-only system prompt](qwen_identity_system_prompt.md) · [Identity validation](results/identity_validation.json) · [Gemini prompt hash verification](gemini_prompt_unchanged.txt)', '',
          'Generation times are CUDA-synchronized and include thinking. Gemini was running concurrently. Passing this two-segment identity test does not establish accuracy across the full benchmark.','']
p=root/'Qwen_memories_two_segments_identity_refined.md';p.write_text('\n'.join(lines))
(root/'Qwen_memories_two_segments_identity_refined.provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')
rendered=p.read_text().replace('`','')
for memory in memories:
 for group in memory.values():
  for text in group:assert text.replace('`','') in rendered
print(p)
print('Verified',episodic+semantic,'verbatim model-generated memory entries')
