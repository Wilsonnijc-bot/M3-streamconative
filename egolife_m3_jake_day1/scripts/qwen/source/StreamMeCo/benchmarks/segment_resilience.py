"""Rollback a segment's partial graph mutations when a cloud API fails."""
import copy
import json
import time
from pathlib import Path
import httpx
import openai


def api_failure(exc):
    seen=set()
    while exc is not None and id(exc) not in seen:
        seen.add(id(exc))
        if isinstance(exc,(httpx.HTTPError,openai.APIError)):
            return True
        if isinstance(exc,(ValueError,RuntimeError)) and any(marker in str(exc) for marker in (
            'Gemini returned empty/truncated', 'Qwen returned empty/truncated', 'Qwen generation failed:', 'VLM response', 'VLM episodic', 'VLM semantic',
            'Failed to get embedding', 'ASR provider', 'transcription HTTP')):
            return True
        exc=exc.__cause__ or exc.__context__
    return False


def transactional_segment(graph, run, metadata, results):
    before=copy.deepcopy(graph.__dict__)
    started=time.perf_counter()
    try:
        result=run()
        result['status']='committed'
        return result
    except Exception as exc:
        # Revert before deciding whether this is a recoverable cloud failure.
        graph.__dict__.clear()
        graph.__dict__.update(before)
        if not api_failure(exc):
            raise
        event={**metadata,'status':'skipped_api_failure',
               'error':f'{type(exc).__name__}: {exc}',
               'latency_ms':(time.perf_counter()-started)*1000,
               'graph_update_rolled_back':True}
        path=Path(results)/'api_failures.jsonl'
        with path.open('a') as f:f.write(json.dumps(event,ensure_ascii=False)+'\n')
        print('SEGMENT_SKIPPED_API_FAILURE '+json.dumps(event,ensure_ascii=False),flush=True)
        return event
