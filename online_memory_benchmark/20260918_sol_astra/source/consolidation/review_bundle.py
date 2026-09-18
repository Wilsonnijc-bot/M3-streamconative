"""Publish exact model/source artifacts in a small checkpoint review folder."""
import hashlib
import shutil
from pathlib import Path
from .common import read,write


def build_review(root='consolidation/runs/live'):
    root=Path(root)
    review=root/'review';review.mkdir(parents=True,exist_ok=True)
    index=['# Exact consolidation replay','',
        'Each checkpoint contains the historical memory replay, MOSS transcription, exact Astra input, and unedited Astra output.',
        'Files appear only once actually produced. Missing model artifacts remain explicitly pending.','',
        '| Checkpoint | Historical memory | MOSS transcript | Exact Astra prompt | Raw Astra output | Updated graph |',
        '| --- | --- | --- | --- | --- | --- |']
    for minutes in (20,40):
        if not (root/f'metadata/prefix_{minutes}.json').exists():
            continue
        case=review/f'{minutes}min';metadata=case/'metadata';metadata.mkdir(parents=True,exist_ok=True)
        sources={}
        replay=Path(f'egolife_m3_jake_day1/results/gemini/replays/memories_{minutes}min.md')
        target=case/'01_memory_replay.md'
        # Saved historical text is copied byte-for-byte, never consolidated retrospectively.
        shutil.copyfile(replay,target);sources[target.name]=str(replay)
        prefix=read(root/f'metadata/prefix_{minutes}.json')
        clip=prefix['segments'][-1]['segment_id']
        graph=Path(f'egolife_m3_jake_day1/provenance/raw/gemini/results/clip_audits/clip_{clip}_graph.json')
        shutil.copyfile(graph,metadata/'source_graph.json');sources['metadata/source_graph.json']=str(graph)
        moss_folder=root/f'moss/prefix_{minutes}'
        moss_text='pending'
        if (moss_folder/'raw_output.json').exists():
            raw=read(moss_folder/'raw_output.json')
            (case/'02_moss_transcript.txt').write_text(raw['text'],encoding='utf-8')
            shutil.copyfile(moss_folder/'raw_output.json',metadata/'moss_raw_output.json')
            sources['02_moss_transcript.txt']=str(moss_folder/'raw_output.json')+'#/text'
            sources['metadata/moss_raw_output.json']=str(moss_folder/'raw_output.json')
            moss_text=f'[Raw transcript]({minutes}min/02_moss_transcript.txt)'
        if (moss_folder/'moss.json').exists():
            moss=read(moss_folder/'moss.json')
            shutil.copyfile(moss_folder/'moss.json',metadata/'moss_segments.json')
            sources['metadata/moss_segments.json']=str(moss_folder/'moss.json')
            timeline=[f'# MOSS timeline — {minutes}-minute checkpoint','',
                f"Input prefix: 0–{moss['cutoff_s']} s. Run: `{moss['run_id']}`.",
                'Times below are relative to the session start. The exact decoded transcript is in `02_moss_transcript.txt`.','']
            for s in moss['segments']:
                timeline.extend([f"**{s['start']:.2f}–{s['end']:.2f} s · {s['speaker']}**",'',s['text'],''])
            (case/'02_moss_timeline.md').write_text('\n'.join(timeline),encoding='utf-8')
            sources['02_moss_timeline.md']='readable rendering of '+str(moss_folder/'moss.json')
        work=root/f'metadata/astra_{minutes}'
        prompt_link=output_link='pending'
        if (work/'llm_input.json').exists():
            payload=read(work/'llm_input.json')
            shutil.copyfile(work/'llm_input.json',metadata/'astra_request.json')
            sources['metadata/astra_request.json']=str(work/'llm_input.json')
            sections=['# Exact Astra prompt','',
                'The instruction and input strings below are reproduced completely. API parameters and the exact JSON request are in `metadata/astra_request.json`.','',
                '## Instructions','',payload['instructions'],'']
            for i,item in enumerate(payload['input']):
                sections.extend([f"## Input {i+1} — {item['role']}",'',item['content'],''])
            (case/'03_astra_prompt.md').write_text('\n'.join(sections),encoding='utf-8')
            sources['03_astra_prompt.md']='complete instruction/input strings from '+str(work/'llm_input.json')
            prompt_link=f'[Prompt]({minutes}min/03_astra_prompt.md)'
        if (work/'llm_output.txt').exists():
            shutil.copyfile(work/'llm_output.txt',case/'04_astra_raw_output.txt')
            sources['04_astra_raw_output.txt']=str(work/'llm_output.txt')
            output_link=f'[Raw output]({minutes}min/04_astra_raw_output.txt)'
        if (work/'llm_response.json').exists():
            shutil.copyfile(work/'llm_response.json',metadata/'astra_raw_response.json')
            sources['metadata/astra_raw_response.json']=str(work/'llm_response.json')
        updated_link='pending'
        summary_path=root/f'checkpoint_{minutes}.json'
        if summary_path.exists():
            from .graph_markdown import render_graph
            version=Path(read(summary_path)['path'])
            graph,state,packet,execution=[read(version/(name+'.json')) for name in ('graph','state','evidence','execution')]
            (case/'05_updated_graph.md').write_text(render_graph(graph,state,packet,execution),encoding='utf-8')
            shutil.copyfile(version/'graph.json',metadata/'updated_graph.json')
            sources['05_updated_graph.md']='complete Markdown rendering of '+str(version/'graph.json')
            sources['metadata/updated_graph.json']=str(version/'graph.json')
            updated_link=f'[Updated graph]({minutes}min/05_updated_graph.md)'
        records={name:{'source':source,'sha256':hashlib.sha256((case/name).read_bytes()).hexdigest()} for name,source in sources.items()}
        write(metadata/'manifest.json',{'checkpoint_minutes':minutes,'cutoff_s':prefix['current_cutoff'],'artifacts':records})
        index.append(f'| {minutes} min | [Replay]({minutes}min/01_memory_replay.md) | {moss_text} | {prompt_link} | {output_link} | {updated_link} |')
        (case/'README.md').write_text('\n'.join([f'# {minutes}-minute exact replay','',
            f"Actual committed cutoff: {prefix['current_cutoff']} seconds.",'',
            '- [Historical memory replay](01_memory_replay.md)',
            '- `02_moss_transcript.txt`: exact decoded MOSS output, when available.',
            '- `02_moss_timeline.md`: readable timestamp/speaker rendering, when available.',
            '- `03_astra_prompt.md`: full instructions and evidence input, when available.',
            '- `04_astra_raw_output.txt`: unedited Astra output, when available.',
            '- `05_updated_graph.md`: complete updated graph with people, observations, all memory nodes and edges, when published.',
            '- `metadata/`: original graph JSON, raw model JSON requests/responses, and source/hash manifest.','']),encoding='utf-8')
    (review/'README.md').write_text('\n'.join(index)+'\n',encoding='utf-8')
    return review


if __name__=='__main__':print(build_review())
