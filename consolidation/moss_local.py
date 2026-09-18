"""Pinned-checkpoint MOSS inference on consecutive committed audio windows."""
import argparse
import hashlib
import time
from pathlib import Path
from .common import read, write, interval
from .moss_runner import prepare_window, normalize_segments, MODEL, parse_output


class LocalWindowMoss:
    """Run the existing pinned local inference CLI in an isolated child process."""
    def __init__(self, checkpoint, revision, repository, *, python=None):
        import sys
        self.checkpoint, self.revision = str(checkpoint), revision
        self.repository, self.python = str(repository), python or sys.executable

    def __call__(self, replay, start_s, directory):
        import os
        import subprocess
        from .moss_alignment import validate_window
        from .common import digest
        directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
        manifest=dict(replay,previous_cutoff=start_s)
        manifest.pop('native_graph',None)
        expected=digest(dict(manifest=manifest,revision=self.revision,checkpoint=self.checkpoint))
        receipt=directory/'request.json';result=directory/'results/window/moss.json'
        if receipt.exists() and read(receipt)['digest']!=expected:
            raise ValueError('local MOSS retry input changed')
        write(receipt,dict(digest=expected))
        observed = [s for s in replay['segments'] if not s.get('gap') and
            s['absolute_end_seconds']-replay['origin_seconds'] > start_s and
            s['absolute_start_seconds']-replay['origin_seconds'] < replay['current_cutoff']]
        inference_end=min(replay['current_cutoff'],max(
            (s['absolute_end_seconds']-replay['origin_seconds'] for s in observed),
            default=replay['current_cutoff']))
        if not result.exists():
            if not observed:
                value=dict(session_id=replay['session_id'],start_s=start_s,
                    cutoff_s=replay['current_cutoff'],timestamp_origin='session',
                    run_id=replay['session_id']+'/no_observed_media/'+str(start_s),
                    segments=[],status='no_observed_media',model_called=False)
                write(result,value)
                return value
            # A declared missing-media tail has no audio to transcribe. Retain
            # internal gaps and all recorded silence, but do not manufacture a
            # long silent tail that can provoke repetitive hallucinated speech.
            manifest=dict(manifest,current_cutoff=inference_end,segments=[s for s in manifest['segments']
                if s['absolute_start_seconds']-replay['origin_seconds']<inference_end])
            write(directory/'window.json',manifest)
            env=dict(os.environ)
            env['PYTHONPATH']=os.pathsep.join([str(Path(__file__).resolve().parents[1]),
                self.repository,env.get('PYTHONPATH','')])
            command=[self.python,'-u','-m','consolidation.moss_local',
                '--manifest',str(directory/'window.json'),'--media-root','/',
                '--checkpoint',self.checkpoint,'--revision',self.revision,
                '--output',str(directory/'results')]
            with (directory/'inference.log').open('a') as log:
                subprocess.run(command,env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
        value=read(result)
        validate_window(value,replay['session_id'],start_s,inference_end)
        if inference_end<replay['current_cutoff']:
            value=dict(value,cutoff_s=replay['current_cutoff'],inference_cutoff_s=inference_end,
                       unobserved_tail=[inference_end,replay['current_cutoff']])
        write(directory/'moss.json',value)
        return value


def manifest_windows(filenames, initial_start=0):
    previous_cutoffs={}
    for filename in filenames:
        replay=read(filename)
        cutoff=replay['current_cutoff']
        start=replay.get('previous_cutoff',previous_cutoffs.get(replay['session_id'],initial_start))
        interval(start,cutoff)
        if replay['session_id'] in previous_cutoffs and start!=previous_cutoffs[replay['session_id']]:
            raise ValueError('MOSS manifests do not describe consecutive windows')
        previous_cutoffs[replay['session_id']]=cutoff
        yield filename,replay,start


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--manifest',nargs='+',required=True)
    p.add_argument('--media-root',required=True)
    p.add_argument('--checkpoint',required=True)
    p.add_argument('--revision',required=True)
    p.add_argument('--output',required=True)
    p.add_argument('--preflight',action='store_true')
    p.add_argument('--start-s',type=float,default=0,help='first window start unless manifest supplies previous_cutoff')
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
    for filename,replay,start in manifest_windows(args.manifest,args.start_s):
        assert all((Path(args.media_root)/s['source']).is_file() for s in replay['segments'] if not s.get('gap'))
    print('MOSS_PREFLIGHT_OK',torch.__version__,transformers.__version__,torch.cuda.get_device_name(0),flush=True)
    if args.preflight:return
    output=Path(args.output); output.mkdir(parents=True,exist_ok=True)
    started=time.monotonic()
    model=AutoModelForCausalLM.from_pretrained(str(checkpoint),trust_remote_code=True,
        dtype=torch.bfloat16,attn_implementation='sdpa').to('cuda').eval()
    processor=AutoProcessor.from_pretrained(str(checkpoint),trust_remote_code=True)
    print('MODEL_LOADED',round(time.monotonic()-started,2),flush=True)
    for filename,replay,start in manifest_windows(args.manifest,args.start_s):
        cutoff=replay['current_cutoff']
        duration=cutoff-start
        run_id=replay['session_id']+'/moss_'+str(start)+'_'+str(cutoff)+'/'+args.revision[:12]
        folder=output/Path(filename).stem
        folder.mkdir(parents=True,exist_ok=True)
        wav=prepare_window(replay,args.media_root,folder/'window.wav',start)
        messages=build_transcription_messages(wav)
        write(folder/'model_input.json',{'messages':messages,'audio_sha256':hashlib.sha256(wav.read_bytes()).hexdigest(),
            'start_s':start,'cutoff_s':cutoff,'timestamp_origin':'window','model':MODEL,'revision':args.revision})
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
            bounded=dict(raw,start=max(0,raw['start']),end=min(duration,raw['end']))
            try:
                interval(bounded['start'],bounded['end'],duration)
                if not bounded['speaker']:raise ValueError('missing speaker')
            except ValueError:
                anomalies.append({'raw_segment':raw,'action':'excluded_invalid_interval_or_speaker'})
                continue
            if bounded!=raw:anomalies.append({'raw_segment':raw,'action':'bounded_to_input_audio'})
            normalized.append(bounded)
        if not normalized:raise ValueError('MOSS returned no valid speech segments')
        token_count=result.get('generated_tokens',result.get('num_generated_tokens'))
        if token_count is not None and token_count>=65536:raise ValueError('MOSS generation reached token cap')
        normalized=normalize_segments(normalized,start,cutoff)
        moss=dict(session_id=replay['session_id'],start_s=start,cutoff_s=cutoff,timestamp_origin='session',
            run_id=run_id,model=MODEL,revision=args.revision,
            audio_sha256=hashlib.sha256(wav.read_bytes()).hexdigest(),segments=normalized,
            inference_config={'max_new_tokens':65536,'do_sample':False,'dtype':'bfloat16','attention':'sdpa'},
            runtime={'torch':torch.__version__,'transformers':transformers.__version__,'elapsed_s':elapsed},
            anomalies=anomalies,epistemic_status='model-generated reference evidence, not ground truth')
        write(folder/'moss.json',moss)
        print('WINDOW_COMPLETE',start,cutoff,'segments',len(normalized),'speakers',len({s['speaker'] for s in normalized}),
              'last_end',max(s['end'] for s in normalized),'elapsed_s',round(elapsed,2),flush=True)
    print('MOSS_ALL_COMPLETE',flush=True)


if __name__=='__main__':main()
