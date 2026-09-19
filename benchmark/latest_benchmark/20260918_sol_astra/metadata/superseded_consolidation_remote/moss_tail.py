"""Targeted follow-up over the same full audio, with explicit prior speaker anchors."""
import argparse
import hashlib
import time
from pathlib import Path
from .common import read,write
from .moss_runner import parse_output


def main():
    p=argparse.ArgumentParser();p.add_argument('--folder',required=True);p.add_argument('--checkpoint',required=True);a=p.parse_args()
    folder=Path(a.folder);moss=read(folder/'moss.json');original=read(folder/'raw_output.json')
    import torch
    from transformers import AutoModelForCausalLM,AutoProcessor
    from moss_transcribe_diarize.inference_utils import build_transcription_messages,generate_transcription
    model=AutoModelForCausalLM.from_pretrained(a.checkpoint,trust_remote_code=True,dtype=torch.bfloat16,attn_implementation='sdpa').to('cuda').eval()
    processor=AutoProcessor.from_pretrained(a.checkpoint,trust_remote_code=True)
    start=max(s['end'] for s in moss['segments'])
    anchors=moss['segments'][-20:]
    import json
    prompt=f'请只转写这份完整音频最后尚未完成的部分，从{start:.2f}秒到{moss["cutoff_s"]:.2f}秒。不要从开头重新转写。时间戳必须使用原始整段音频的绝对秒数，不要归零。下面是同一段音频最近的已完成转写，沿用这些说话人编号；不能确认则使用新编号。每段格式为[起始秒数][Sxx]语音文本[结束秒数]。\n已有参考：'+json.dumps(anchors,ensure_ascii=False)
    wav=folder/'prefix.wav'
    assert hashlib.sha256(wav.read_bytes()).hexdigest()==moss['audio_sha256']
    messages=build_transcription_messages(wav,prompt=prompt)
    write(folder/'tail_input.json',{'messages':messages,'audio_sha256':moss['audio_sha256'],'max_new_tokens':1024,'prior_speaker_anchors':anchors})
    print('TAIL_BEGIN',start,moss['cutoff_s'],flush=True);tick=time.monotonic()
    result=generate_transcription(model,processor,messages,max_new_tokens=1024,do_sample=False,device=torch.device('cuda'),dtype=torch.bfloat16)
    result['elapsed_s']=time.monotonic()-tick
    write(folder/'tail_output.json',result)
    segments=parse_output(result['text'])
    if result['generated_tokens']>=1024:raise ValueError('tail output hit cap')
    if not segments or any(s['start']<start-1 for s in segments):raise ValueError('tail request ignored focus interval')
    if max(s['end'] for s in segments)<moss['cutoff_s']-3:raise ValueError('tail still incomplete')
    if any(s['end']>moss['cutoff_s']+1 for s in segments):raise ValueError('tail timestamp beyond audio')
    for s in segments:s['end']=min(s['end'],moss['cutoff_s'])
    write(folder/'moss_initial.json',moss)
    moss['segments'].extend(segments)
    moss['continuation']={'method':'same full audio, targeted tail request with explicit prior speaker anchors',
        'start_s':start,'segments':len(segments),'elapsed_s':result['elapsed_s'],'raw_initial_text_ended_mid_timestamp':True}
    moss['anomalies'].append({'action':'initial_raw_text_incomplete; tail supplied by explicit follow-up; raw calls retained'})
    write(folder/'moss.json',moss)
    print('TAIL_COMPLETE',len(segments),max(s['end'] for s in segments),flush=True)


if __name__=='__main__':main()
