"""Fail-closed Gemini reasoning with append-only per-request telemetry."""
import json
import os
import time
import uuid
from pathlib import Path
import httpx
import cloud_http

MODEL = 'gemini-3.8-flash'
CONTEXT = {}

def append(event, name='gemini_calls.jsonl'):
    root = os.environ.get('EGOLIFE_RESULTS')
    if root:
        path = Path(root) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('a') as f:
            f.write(json.dumps(event, ensure_ascii=False) + '\n')

def call(messages, purpose, max_tokens=8192):
    key = os.environ.get('API_302_KEY')
    if not key:
        raise RuntimeError('API_302_KEY missing; no alternate model permitted')
    event = dict(CONTEXT, call_id=str(uuid.uuid4()), purpose=purpose, model=MODEL,
                 provider='302.ai', request_start=time.time(), ttft_ms=None,
                 first_response=None, input_tokens=None, output_tokens=None)
    started = time.perf_counter()
    event["transport"] = {}
    try:
        response = cloud_http.post(
            'https://' + os.environ.get('API_302_DIRECT_IP', '20.255.184.187') + '/v1/chat/completions',
            direct=True, timeout=900, metrics=event["transport"],
            headers={'Host':'api.302.ai', 'Authorization':'Bearer '+key},
            json={'model':MODEL, 'messages':messages, 'temperature':0.000001,
                  'max_tokens':max_tokens})
        response.raise_for_status()
        body = response.json()
        event['returned_model'] = body.get('model')
        if body.get('model') != MODEL:
            raise RuntimeError(f'Requested {MODEL}, endpoint returned {body.get("model")!r}')
        choice = body['choices'][0]
        event['finish_reason'] = choice.get('finish_reason')
        event['response'] = choice['message'].get('content') or ''
        usage = body.get('usage') or {}
        event.update(input_tokens=usage.get('prompt_tokens'), output_tokens=usage.get('completion_tokens'), total_tokens=usage.get('total_tokens'))
        if not event['response'] or choice.get('finish_reason') == 'length':
            raise RuntimeError('Gemini returned empty/truncated output')
    except Exception as exc:
        event['error'] = f'{type(exc).__name__}: {exc}'
        raise
    finally:
        event['request_end'] = time.time()
        event['latency_ms'] = (time.perf_counter()-started)*1000
        event['client_wall_clock_latency_ms'] = event['latency_ms']
        event['api_request_wall_clock_latency_ms'] = event['latency_ms']
        append(event)
    return event

def text_call(backend, prompt, qwen_url=None, purpose='final_answer'):
    if backend != 'gemini':
        raise RuntimeError('This benchmark permits cloud Gemini only')
    return call([{'role':'user','content':prompt}], purpose)

def configure(results, phase):
    os.environ['EGOLIFE_GEMINI_ONLY'] = '1'
    os.environ['EGOLIFE_RESULTS'] = str(results)
    CONTEXT.clear()
    CONTEXT.update(phase=phase, question_id=None, method=None)
    path = Path(results) / 'model_manifest.json'
    manifest = {'reasoning_model':MODEL, 'provider':'302.ai', 'fallbacks':False,
                'memory_lineage':'fresh Gemini-only shared build',
                'preprocessing':'existing ASR, face and speaker recognition; no alternate reasoning LLM',
                'ttft':'not exposed by non-streaming endpoint'}
    if path.exists() and json.loads(path.read_text()) != manifest:
        raise RuntimeError('Existing results have incompatible model lineage')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2)+'\n')
    print('REASONING_MODEL='+MODEL+' provider=302.ai fallbacks=disabled', flush=True)
