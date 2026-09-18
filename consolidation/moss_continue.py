"""Continue a prematurely ended MOSS transcript using the SAME full audio and prefix."""
import argparse
import hashlib
import time
from pathlib import Path
from .common import read,write
from .moss_runner import parse_output


def main():
    p=argparse.ArgumentParser();p.add_argument('--folder',required=True);p.add_argument('--checkpoint',required=True);a=p.parse_args()
    folder=Path(a.folder)
    original=read(folder/'raw_output.json');moss=read(folder/'moss.json');model_input=read(folder/'model_input.json')
    import torch
    from transformers import AutoModelForCausalLM,AutoProcessor
    from moss_transcribe_diarize.inference_utils import prepare_inputs,build_transcription_messages
    print('CONTINUATION_PREFLIGHT',torch.arange(8,device='cuda').square().sum().item(),flush=True)
    model=AutoModelForCausalLM.from_pretrained(a.checkpoint,trust_remote_code=True,dtype=torch.bfloat16,
                                             attn_implementation='sdpa').to('cuda').eval()
    processor=AutoProcessor.from_pretrained(a.checkpoint,trust_remote_code=True)
    wav=folder/'prefix.wav'
    assert hashlib.sha256(wav.read_bytes()).hexdigest()==model_input['audio_sha256']
    messages=build_transcription_messages(wav)
    with torch.amp.autocast('cuda',dtype=torch.bfloat16):
        inputs=prepare_inputs(processor,messages,device=torch.device('cuda')).to('cuda')
    prefix=processor.tokenizer.encode(original['text'],add_special_tokens=False,return_tensors='pt').to('cuda')
    inputs['input_ids']=torch.cat([inputs['input_ids'],prefix],dim=1)
    inputs['attention_mask']=torch.cat([inputs['attention_mask'],torch.ones_like(prefix)],dim=1)
    write(folder/'continuation_input.json',{'model_input':model_input,'assistant_prefix':original['text'],
        'input_tokens':inputs['input_ids'].shape[-1],'max_new_tokens':8192,'do_sample':False})
    print('CONTINUATION_BEGIN',inputs['input_ids'].shape[-1],flush=True)
    start=time.monotonic()
    with torch.inference_mode(),torch.amp.autocast('cuda',dtype=torch.bfloat16):
        generated=model.generate(input_ids=inputs['input_ids'],attention_mask=inputs['attention_mask'],
            input_features=inputs['input_features'],audio_feature_lengths=inputs['audio_feature_lengths'],
            audio_chunk_mapping=inputs['audio_chunk_mapping'],max_new_tokens=8192,do_sample=False)
    ids=generated[0,inputs['input_ids'].shape[-1]:]
    suffix=processor.tokenizer.decode(ids,skip_special_tokens=True)
    combined=original['text']+suffix
    result={'text':combined,'initial_generated_tokens':original['generated_tokens'],
        'continuation_generated_tokens':int(ids.numel()),'final_token_id':int(ids[-1]),
        'eos_token_id':model.generation_config.eos_token_id,'continuation_elapsed_s':time.monotonic()-start,
        'method':'same full audio and exact assistant transcript prefix; no independently diarized window concatenation'}
    write(folder/'continuation_output.json',dict(result,suffix=suffix))
    segments=parse_output(combined)
    if ids.numel()>=8192:raise ValueError('continuation hit output cap')
    if not segments:raise ValueError('no parsed segments')
    anomalies=[];normalized=[]
    for segment in segments:
        if segment['start']>=moss['cutoff_s'] or segment['end']<=segment['start']:
            anomalies.append({'raw_segment':segment,'action':'excluded_invalid_interval'});continue
        if segment['end']>moss['cutoff_s']:
            anomalies.append({'raw_segment':dict(segment),'action':'bounded_to_input_audio'})
            segment=dict(segment,end=moss['cutoff_s'])
        normalized.append(segment)
    assert max(s['end'] for s in normalized)>max(s['end'] for s in moss['segments'])
    write(folder/'raw_output_initial.json',original)
    write(folder/'moss_initial.json',moss)
    write(folder/'raw_output.json',result)
    moss.update(segments=normalized,anomalies=moss['anomalies']+anomalies,
                continuation={'generated_tokens':int(ids.numel()),'elapsed_s':result['continuation_elapsed_s'],'same_full_audio':True})
    write(folder/'moss.json',moss)
    print('CONTINUATION_COMPLETE',len(normalized),max(s['end'] for s in normalized),result['continuation_generated_tokens'],flush=True)


if __name__=='__main__':main()
