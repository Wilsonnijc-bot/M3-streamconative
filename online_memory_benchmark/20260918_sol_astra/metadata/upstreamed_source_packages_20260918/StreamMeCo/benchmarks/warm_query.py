"""Warm retrieval engines with a fixed non-benchmark probe before trial timing."""
import json
import hashlib
import sys
import time
from pathlib import Path

PROBE='Describe a recent observed activity.'

def prepare_warm_query(run_probe, results, method, snapshot_index, load_ms):
    started=time.perf_counter()
    event={'method':method,'snapshot_index':snapshot_index,'purpose':'retrieval_warmup',
           'probe':PROBE,'snapshot_load_ms':load_ms,'included_in_qa_metrics':False,
           'question_query_cache_primed':False,'request_start':time.time(),
           'warmup_code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
           'entrypoint_sha256':hashlib.sha256(Path(sys.argv[0]).read_bytes()).hexdigest() if Path(sys.argv[0]).is_file() else None}
    try:
        output=run_probe(PROBE)
        metrics=output[-1]
        event.update(status='success',retrieval_metrics=metrics)
        return event
    except Exception as exc:
        event.update(status='failed',error=f'{type(exc).__name__}: {exc}')
        raise
    finally:
        event.update(request_end=time.time(),warmup_ms=(time.perf_counter()-started)*1000)
        with (Path(results)/'retrieval_warmup.jsonl').open('a') as handle:
            handle.write(json.dumps(event,ensure_ascii=False)+'\n')
