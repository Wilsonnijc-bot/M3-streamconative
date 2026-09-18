"""Pinned-checkpoint MOSS inference on full committed audio prefixes."""
import argparse
import hashlib
import time
from pathlib import Path
from .common import read, write, interval
from .moss_runner import prepare_prefix, MODEL, parse_output


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--manifest',nargs='+',required=True)
    p.add_argument('--media-root',required=True)
    p.add_argument('--checkpoint',required=True)
    p.add_argument('--revision',required=True)
    p.add_argument('--output',required=True)
    p.add_argument('--preflight',action='store_true')
    args=p.parse_args()
    import torch
    import transformers
    from transformers import AutoModelForCausalLM, AutoProcessor
    from moss_transcribe_diarize import parse_transcript
    from moss_transcribe_diarize.inference_utils import build_transcription_messages, generate_transcription
    assert torch.cuda.is_available()
    assert torch.arange(8,device='cuda').square().sum().item()==140
    checkpoint=Path(args.checkpoint)
    assert (checkpoint/'config.json').is_file()
    for filename in args.manifest:
        replay=read(filename)
        assert all((Path(args.media_root)/s['source']).is_file() for s in replay['segments'])
    print('MOSS_PREFLIGHT_OK',torch.__version__,transformers.__version__,torch.cuda.get_device_name(0),flush=True)
    if args.preflight:return
    output=Path(args.output); output.mkdir(parents=True,exist_ok=True)
    started=time.monotonic()
    model=AutoModelForCausalLM.from_pretrained(str(checkpoint),trust_remote_code=True,
        dtype=torch.bfloat16,attn_implementation='sdpa').to('cuda').eval()
    processor=AutoProcessor.from_pretrained(str(checkpoint),trust_remote_code=True)
    print('MODEL_LOADED',round(time.monotonic()-started,2),flush=True)
    for filename in args.manifest:
        replay=read(filename)
        cutoff=replay['current_cutoff']
        run_id=replay['session_id']+'/moss_'+str(cutoff)+'/'+args.revision[:12]
        folder=output/Path(filename).stem
        folder.mkdir(parents=True,exist_ok=True)
        wav=prepare_prefix(replay,args.media_root,folder/'prefix.wav')
        messages=build_transcription_messages(wav)
        write(folder/'model_input.json',{'messages':messages,'audio_sha256':hashlib.sha256(wav.read_bytes()).hexdigest(),
            'cutoff_s':cutoff,'model':MODEL,'revision':args.revision})
        tick=time.monotonic()
        print('INFERENCE_BEGIN',cutoff,flush=True)
        result=generate_transcription(model,processor,messages,max_new_tokens=65536,do_sample=False,
            device=torch.device('cuda'),dtype=torch.bfloat16,
            input_callback=lambda n:print('PROMPT_TOKENS',n,flush=True),
            token_callback=lambda n:print('GENERATED_TOKENS',n,flush=True) if n%1000==0 else None)
        elapsed=time.monotonic()-tick
        write(folder/'raw_output.json',result)
        print('RAW_RESULT', {k:v for k,v in result.items() if k!='text'},flush=True)
        parse_output(result['text'])  # Fail closed on an incomplete raw tail before exposing moss.json.
        normalized=[]; anomalies=[]
        for item in parse_transcript(result['text']):
            raw={'start':float(item.start),'end':float(item.end),'speaker':item.speaker,'text':item.text}
            bounded=dict(raw,start=max(0,raw['start']),end=min(cutoff,raw['end']))
            try:
                interval(bounded['start'],bounded['end'],cutoff)
                if not bounded['speaker']:raise ValueError('missing speaker')
            except ValueError:
                anomalies.append({'raw_segment':raw,'action':'excluded_invalid_interval_or_speaker'})
                continue
            if bounded!=raw:anomalies.append({'raw_segment':raw,'action':'bounded_to_input_audio'})
            normalized.append(bounded)
        if not normalized:raise ValueError('MOSS returned no valid speech segments')
        token_count=result.get('generated_tokens',result.get('num_generated_tokens'))
        if token_count is not None and token_count>=65536:raise ValueError('MOSS generation reached token cap')
        moss=dict(session_id=replay['session_id'],cutoff_s=cutoff,run_id=run_id,model=MODEL,revision=args.revision,
            audio_sha256=hashlib.sha256(wav.read_bytes()).hexdigest(),segments=normalized,
            inference_config={'max_new_tokens':65536,'do_sample':False,'dtype':'bfloat16','attention':'sdpa'},
            runtime={'torch':torch.__version__,'transformers':transformers.__version__,'elapsed_s':elapsed},
            anomalies=anomalies,epistemic_status='model-generated reference evidence, not ground truth')
        write(folder/'moss.json',moss)
        print('PREFIX_COMPLETE',cutoff,'segments',len(normalized),'speakers',len({s['speaker'] for s in normalized}),
              'last_end',max(s['end'] for s in normalized),'elapsed_s',round(elapsed,2),flush=True)
    print('MOSS_ALL_COMPLETE',flush=True)


if __name__=='__main__':main()
