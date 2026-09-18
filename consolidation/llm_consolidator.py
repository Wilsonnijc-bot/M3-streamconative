import json
import os
import urllib.request
from pathlib import Path
from .common import dumps, write
from .schema import PATCH_SCHEMA
from .prompt_packet import prepare_prompt, compact


def request_payload(packet, model, directory=None):
    system = (Path(__file__).parent/'prompts/system.md').read_text()
    model_packet = prepare_prompt(packet, directory)
    return {'model':model, 'messages':[
        {'role':'system','content':system+'\n\nPatch JSON Schema:\n'+dumps(PATCH_SCHEMA)},
        {'role':'user','content':compact(model_packet)}],
        'response_format':{'type':'json_object'}}


def propose(packet, directory, model, endpoint=None, key_env='CONSOLIDATION_API_KEY', patch_file=None):
    directory = Path(directory)
    payload = request_payload(packet, model, directory)
    write(directory/'llm_input.json', payload)
    if patch_file:
        raw = Path(patch_file).read_text()
        metadata = {'backend':'recorded_patch','model':model,'source':str(patch_file)}
    else:
        if not endpoint:
            raise ValueError('configure an LLM endpoint or provide a recorded patch')
        headers = {'Content-Type':'application/json'}
        if os.environ.get(key_env):
            headers['Authorization']='Bearer '+os.environ[key_env]
        req = urllib.request.Request(endpoint.rstrip('/')+'/chat/completions',
            data=dumps(payload).encode(),headers=headers)
        with urllib.request.urlopen(req, timeout=600) as response:
            result=json.load(response)
        write(directory/'llm_response.json', result)
        choice=result['choices'][0]
        if choice.get('finish_reason') not in (None,'stop'):
            raise ValueError('incomplete LLM response: '+str(choice.get('finish_reason')))
        raw=choice['message']['content']
        metadata={'backend':'live','model':model,'returned_model':result.get('model'),'usage':result.get('usage')}
    directory.mkdir(parents=True,exist_ok=True)
    (directory/'llm_output.txt').write_text(raw)
    write(directory/'llm_metadata.json',metadata)
    patch=json.loads(raw)
    write(directory/'patch.json',patch)
    return patch


def propose_official(packet, directory, api_config, model='gpt-6-astra'):
    """Official Responses API with durable background request ID and exact artifacts."""
    import time
    import urllib.error
    from urllib.parse import urlparse
    from .common import read, digest
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    config=read(api_config)[model]
    endpoint=(config.get('base_url') or 'https://api.openai.com/v1').rstrip('/')
    if urlparse(endpoint).hostname!='api.openai.com':
        raise ValueError('official run requires api.openai.com')
    key=os.environ.get(config.get('api_key_env','')) or config.get('api_key')
    if not key:raise ValueError('official model API key is missing')
    request_path=directory/'llm_input.json'
    chat=request_payload(packet,model,None if request_path.exists() else directory)
    payload={'model':model,'instructions':chat['messages'][0]['content'],
        'input':[chat['messages'][1], {'role':'developer','content':'Return the consolidation patch as a JSON object.'}],
        'reasoning':{'effort':config.get('reasoning_effort','high')},
        'text':{'format':{'type':'json_object'}},'max_output_tokens':65536,
        'background':True,'store':True}
    fingerprint=digest(payload)
    if request_path.exists() and read(request_path)!=payload:
        raise ValueError('work directory already contains a different model request')
    if request_path.exists():
        prepare_prompt(packet,directory)
    write(request_path,payload)
    headers={'Authorization':'Bearer '+key,'Content-Type':'application/json','User-Agent':'StreamMeCo-consolidation/0.1'}
    def call(path,body=None):
        request=urllib.request.Request(endpoint+path,headers=headers,
            data=dumps(body).encode() if body is not None else None)
        try:
            with urllib.request.urlopen(request,timeout=120) as response:return json.load(response)
        except urllib.error.HTTPError as error:
            detail=json.loads(error.read())
            write(directory/'api_error.json',{'status':error.code,'error':detail.get('error')})
            raise RuntimeError('Official Responses API HTTP '+str(error.code)) from None
    status_path=directory/'response_status.json'
    if status_path.exists():
        status=read(status_path)
        if status['request_digest']!=fingerprint:raise ValueError('resume request mismatch')
        result=call('/responses/'+status['response_id'])
    else:
        result=call('/responses',payload)
        write(status_path,{'request_digest':fingerprint,'response_id':result['id'],'status':result['status']})
    deadline=time.monotonic()+3600
    while result['status'] in ('queued','in_progress'):
        write(status_path,{'request_digest':fingerprint,'response_id':result['id'],'status':result['status']})
        if time.monotonic()>deadline:raise TimeoutError('background response still running; resume using saved response ID')
        time.sleep(5)
        result=call('/responses/'+result['id'])
    write(directory/'llm_response.json',result)
    write(status_path,{'request_digest':fingerprint,'response_id':result['id'],'status':result['status']})
    if result['status']!='completed':raise ValueError('official response did not complete: '+result['status'])
    raw=''.join(c['text'] for item in result['output'] if item['type']=='message'
                for c in item['content'] if c['type']=='output_text')
    (directory/'llm_output.txt').write_text(raw)
    write(directory/'llm_metadata.json',{'backend':'official_responses','model':model,
        'returned_model':result['model'],'response_id':result['id'],'usage':result.get('usage'),
        'reasoning':result.get('reasoning'),'request_digest':fingerprint,'endpoint':endpoint})
    patch=json.loads(raw)
    write(directory/'patch.json',patch)
    return patch
