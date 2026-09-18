"""MOSS full-prefix input and inference, using the upstream transcription endpoint.
Protocol: https://huggingface.co/OpenMOSS-Team/MOSS-Transcribe-Diarize
"""
import hashlib
import json
import os
import re
import subprocess
import urllib.request
import uuid
import wave
from pathlib import Path
from .common import interval, write

MODEL='OpenMOSS-Team/MOSS-Transcribe-Diarize'


def parse_output(text):
    pattern=r'\[([0-9]+(?:\.[0-9]+)?)\]\[([^\]]+)\](.*?)\[([0-9]+(?:\.[0-9]+)?)\]'
    segments=[]
    for m in re.finditer(pattern,text,re.S):
        segments.append(dict(start=float(m[1]),end=float(m[4]),speaker=m[2],text=m[3]))
    residue=re.sub(pattern,'',text,flags=re.S).strip()
    if residue:
        raise ValueError('MOSS output contains unparsed or truncated text')
    if not segments and text.strip():
        raise ValueError('MOSS output contains no parseable diarized segments')
    return segments


def prepare_prefix(replay, media_root, destination, ffmpeg='ffmpeg'):
    """Render onto the source clock including silence at source gaps (16k mono PCM)."""
    destination=Path(destination)
    destination.parent.mkdir(parents=True,exist_ok=True)
    rate=16000
    # A prefix of an hour uses ~115 MB; disk-backed writes avoid collecting it in memory.
    with wave.open(str(destination),'wb') as out:
        out.setnchannels(1); out.setsampwidth(2); out.setframerate(rate)
        cursor=0
        for segment in replay['segments']:
            start=round((segment['absolute_start_seconds']-replay['origin_seconds'])*rate)
            stop=round((segment['absolute_end_seconds']-replay['origin_seconds'])*rate)
            if start<cursor:
                raise ValueError('overlapping source segments')
            out.writeframes(b'\0\0'*(start-cursor))
            source=Path(media_root)/segment['source']
            if not source.exists():
                raise FileNotFoundError(source)
            command=[ffmpeg,'-v','error','-ss',str(segment['start_seconds_in_source']),'-i',str(source),
                     '-t',str((stop-start)/rate),'-f','s16le','-ac','1','-ar',str(rate),'pipe:1']
            pcm=subprocess.run(command,check=True,capture_output=True).stdout
            needed=(stop-start)*2
            if len(pcm)<needed-rate//5:
                raise ValueError('source audio is shorter than its committed segment')
            out.writeframes(pcm[:needed].ljust(needed,b'\0'))
            cursor=stop
    return destination


def run_moss(audio_path,session_id,cutoff,run_id,endpoint,output,key_env='MOSS_API_KEY',revision='server-unspecified'):
    audio_path=Path(audio_path)
    with wave.open(str(audio_path),'rb') as handle:
        duration=handle.getnframes()/handle.getframerate()
    if abs(duration-cutoff)>0.01:
        raise ValueError('MOSS input must match the committed prefix duration')
    boundary=uuid.uuid4().hex
    chunks=[]
    for name,value in {'model':MODEL,'response_format':'verbose_json','max_new_tokens':'65536'}.items():
        chunks.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode())
    chunks.extend([f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="prefix.wav"\r\nContent-Type: audio/wav\r\n\r\n'.encode(),
                   audio_path.read_bytes(),f'\r\n--{boundary}--\r\n'.encode()])
    headers={'Content-Type':'multipart/form-data; boundary='+boundary}
    if os.environ.get(key_env):
        headers['Authorization']='Bearer '+os.environ[key_env]
    request=urllib.request.Request(endpoint.rstrip('/')+'/audio/transcriptions',data=b''.join(chunks),headers=headers)
    with urllib.request.urlopen(request,timeout=3600) as response:
        raw=json.load(response)
    write(str(output)+'.raw.json',raw)
    if raw.get('finish_reason')=='length':
        raise ValueError('MOSS output was truncated')
    segments=raw.get('segments')
    if segments is None:
        segments=parse_output(raw['text'])
    normalized=[]
    for item in segments:
        interval(item['start'],item['end'],cutoff)
        if not item.get('speaker'):
            raise ValueError('MOSS returned a segment without speaker identity')
        normalized.append({k:item[k] for k in ('start','end','speaker','text')})
    result=dict(session_id=session_id,cutoff_s=cutoff,run_id=run_id,model=MODEL,revision=revision,
        audio_sha256=hashlib.sha256(audio_path.read_bytes()).hexdigest(),segments=normalized,
        inference_config={'max_new_tokens':65536,'response_format':'verbose_json'},
        epistemic_status='reference evidence, not ground truth')
    write(output,result)
    return result
