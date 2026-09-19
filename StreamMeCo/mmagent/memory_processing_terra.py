"""Official Terra vision memory construction using the native M3 context/updates."""
import hashlib
import json
import os
from pathlib import Path
import time

from .memory_processing_qwen import generate_video_context, process_memories, _normalize_memory
from .prompts import prompt_generate_memory_with_ids_sft


def build_request(frames, faces, voices, source_fps, target_fps=2):
    if not frames:
        raise ValueError('Terra memory construction requires observed video frames')
    if source_fps<=0 or target_fps<=0 or target_fps>source_fps:
        raise ValueError('invalid construction frame sampling rate')
    context=generate_video_context(frames,faces,voices,None)
    content=[dict(type='input_text',text=prompt_generate_memory_with_ids_sft+
        '\nReturn JSON with nonempty video_description and high_level_conclusions string arrays. '
        'Use only these chronological clip frames and the supplied face/voice evidence.')]
    previous=-1
    for index,frame in enumerate(frames):
        bucket=int(index*target_fps/source_fps)
        if bucket==previous:continue
        previous=bucket
        content.extend([dict(type='input_text',text=f'Clip time {index/source_fps:.3f} seconds'),
                        dict(type='input_image',image_url='data:image/jpeg;base64,'+frame)])
    for item in context:
        if item['type']=='text':content.append(dict(type='input_text',text=item['content']))
        elif item['type']=='images/jpeg':
            for label,frame in item['content']:
                content.extend([dict(type='input_text',text=label),
                    dict(type='input_image',image_url='data:image/jpeg;base64,'+frame)])
    return dict(model='gpt-5.6-terra',reasoning={'effort':'medium'},
        input=[dict(role='user',content=content)],text={'format':{'type':'json_object'}},
        max_output_tokens=8192,store=True)


def generate_memories(base64_frames,faces_list,voices_list,video_path,model_type='sft',metrics=None):
    from openai import OpenAI
    import base64
    import uuid
    metrics=metrics if metrics is not None else {}
    started=time.perf_counter()
    config=json.loads(Path('configs/processing_config.json').read_text())
    payload=build_request(base64_frames,faces_list,voices_list,config['fps'],config.get('memory_video_fps',2))
    metrics['context_preparation_ms']=(time.perf_counter()-started)*1000
    directory=Path(os.environ.get('M3_MEMORY_ARTIFACTS','data/memory_api/terra'))
    blobs=directory/'images';blobs.mkdir(parents=True,exist_ok=True)
    job=directory/'requests'/uuid.uuid4().hex;job.mkdir(parents=True)
    provenance=json.loads(json.dumps(payload))
    for item in provenance['input'][0]['content']:
        if item['type']=='input_image':
            data=base64.b64decode(item.pop('image_url').split(',',1)[1])
            digest=hashlib.sha256(data).hexdigest();path=blobs/(digest+'.jpg')
            if not path.exists():path.write_bytes(data)
            item.update(image_sha256=digest,image_path=str(path))
    (job/'request.json').write_text(json.dumps(provenance,ensure_ascii=False))
    tick=time.perf_counter()
    with OpenAI(base_url='https://api.openai.com/v1',max_retries=0,timeout=600) as client:
        response=client.responses.create(**payload)
    elapsed=(time.perf_counter()-tick)*1000
    raw=response.model_dump(mode='json')
    (job/'response.json').write_text(json.dumps(raw,ensure_ascii=False))
    if response.status!='completed' or response.model!='gpt-5.6-terra':
        raise ValueError('Terra memory response model/status mismatch')
    memory=_normalize_memory(response.output_text)
    metrics.update(vlm_ms=elapsed,model=response.model,provider='official_openai_responses',
        reasoning_effort='medium',raw_response=response.output_text,valid_memory_json=True,
        generated_memory=memory,request_artifacts=str(job),usage=raw.get('usage'),
        attempts=[dict(attempt=1,latency_ms=elapsed,model=response.model)],
        episodic_memory_count=len(memory['video_description']),
        semantic_memory_count=len(memory['high_level_conclusions']))
    return memory['video_description'],memory['high_level_conclusions']
