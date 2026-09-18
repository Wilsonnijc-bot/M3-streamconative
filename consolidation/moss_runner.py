"""MOSS window audio and inference, using the upstream transcription endpoint.
Protocol: https://huggingface.co/OpenMOSS-Team/MOSS-Transcribe-Diarize
"""
import hashlib
import json
import os
import re
import subprocess
import tempfile
import urllib.request
import uuid
import wave
from pathlib import Path
from .common import interval, write, read

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
    """Compatibility helper for explicitly requested historical full-prefix audio."""
    replay = dict(replay)
    replay.setdefault('current_cutoff', max(s['absolute_end_seconds'] for s in replay['segments'])
                      - replay['origin_seconds'])
    return prepare_window(replay, media_root, destination, 0, ffmpeg)


def prepare_window(replay, media_root, destination, start_s, ffmpeg='ffmpeg'):
    """Render exactly [start_s, current_cutoff], preserving gaps as 16k mono silence."""
    cutoff = replay['current_cutoff']
    interval(start_s, cutoff)
    destination=Path(destination)
    destination.parent.mkdir(parents=True,exist_ok=True)
    rate=16000
    first_frame, final_frame = round(start_s*rate), round(cutoff*rate)
    with wave.open(str(destination),'wb') as out:
        out.setnchannels(1); out.setsampwidth(2); out.setframerate(rate)
        cursor=first_frame
        for segment in replay['segments']:
            original_start=round((segment['absolute_start_seconds']-replay['origin_seconds'])*rate)
            original_stop=round((segment['absolute_end_seconds']-replay['origin_seconds'])*rate)
            start, stop = max(first_frame, original_start), min(final_frame, original_stop)
            if stop <= start:
                continue
            if start<cursor:
                raise ValueError('overlapping source segments')
            out.writeframes(b'\0\0'*(start-cursor))
            if segment.get('gap'):
                out.writeframes(b'\0\0'*(stop-start))
                cursor=stop
                continue
            source=Path(media_root)/segment['source']
            if not source.exists():
                raise FileNotFoundError(source)
            offset=segment['start_seconds_in_source'] + (start-original_start)/rate
            command=[ffmpeg,'-v','error','-ss',str(offset),'-i',str(source),
                     '-t',str((stop-start)/rate),'-f','s16le','-ac','1','-ar',str(rate),'pipe:1']
            pcm=subprocess.run(command,check=True,capture_output=True).stdout
            needed=(stop-start)*2
            if len(pcm)<needed-rate//5:
                raise ValueError('source audio is shorter than its committed segment')
            out.writeframes(pcm[:needed].ljust(needed,b'\0'))
            cursor=stop
        out.writeframes(b'\0\0'*(final_frame-cursor))
    return destination


def normalize_segments(segments, start_s, cutoff):
    """Validate model-local timestamps before translating to the session clock."""
    interval(start_s, cutoff)
    normalized=[]
    for item in segments:
        interval(item['start'],item['end'],cutoff-start_s)
        if not item.get('speaker'):
            raise ValueError('MOSS returned a segment without speaker identity')
        normalized.append(dict(start=round(start_s+item['start'],6),
            end=round(start_s+item['end'],6),speaker=item['speaker'],text=item['text']))
    return normalized


def run_moss(audio_path,session_id,cutoff,run_id,endpoint,output,key_env='MOSS_API_KEY',
             revision='server-unspecified',*,start_s=0):
    interval(start_s, cutoff)
    audio_path=Path(audio_path)
    with wave.open(str(audio_path),'rb') as handle:
        duration=handle.getnframes()/handle.getframerate()
    if abs(duration-(cutoff-start_s))>0.01:
        raise ValueError('MOSS input must match the committed window duration')
    boundary=uuid.uuid4().hex
    chunks=[]
    for name,value in {'model':MODEL,'response_format':'verbose_json','max_new_tokens':'65536'}.items():
        chunks.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode())
    chunks.extend([f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="window.wav"\r\nContent-Type: audio/wav\r\n\r\n'.encode(),
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
    normalized=normalize_segments(segments,start_s,cutoff)
    result=dict(session_id=session_id,start_s=start_s,cutoff_s=cutoff,timestamp_origin='session',
        run_id=run_id,model=MODEL,revision=revision,
        audio_sha256=hashlib.sha256(audio_path.read_bytes()).hexdigest(),segments=normalized,
        inference_config={'max_new_tokens':65536,'response_format':'verbose_json'},
        epistemic_status='reference evidence, not ground truth')
    write(output,result)
    return result


class WindowMoss:
    """Consolidation-stage HTTP MOSS callable with exact-window retry caching."""
    def __init__(self, endpoint, media_root, *, revision='server-unspecified', key_env='MOSS_API_KEY'):
        self.endpoint, self.media_root = endpoint, Path(media_root)
        self.revision, self.key_env = revision, key_env

    def __call__(self, replay, start_s, directory):
        from .moss_alignment import validate_window
        directory=Path(directory)
        directory.mkdir(parents=True,exist_ok=True)
        wav=directory/'window.wav'
        path=directory/'moss.json'
        result=None
        if path.exists():
            result=read(path)
            validate_window(result,replay['session_id'],start_s,replay['current_cutoff'])
            if result.get('revision')!=self.revision or result.get('model')!=MODEL:
                raise ValueError('cached MOSS result does not match window model')
        with tempfile.TemporaryDirectory(prefix='.audio-',dir=directory) as staging:
            candidate=prepare_window(replay,self.media_root,Path(staging)/'window.wav',start_s)
            audio_hash=hashlib.sha256(candidate.read_bytes()).hexdigest()
            if result is not None:
                if (result.get('audio_sha256')!=audio_hash or
                        (wav.exists() and hashlib.sha256(wav.read_bytes()).hexdigest()!=audio_hash)):
                    raise ValueError('cached MOSS result does not match window audio')
                if not wav.exists():
                    os.replace(candidate,wav)
                return result
            os.replace(candidate,wav)
        run_id=f"{replay['session_id']}/moss_{start_s:g}_{replay['current_cutoff']:g}/{self.revision}"
        write(directory/'model_input.json',dict(session_id=replay['session_id'],start_s=start_s,
            cutoff_s=replay['current_cutoff'],timestamp_origin='window',audio_sha256=audio_hash,
            model=MODEL,revision=self.revision))
        return run_moss(wav,replay['session_id'],replay['current_cutoff'],run_id,self.endpoint,path,
                        self.key_env,self.revision,start_s=start_s)
