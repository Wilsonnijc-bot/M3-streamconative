import sys,json
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).parents[1]))
from benchmarks.warm_query import prepare_warm_query,PROBE

def test_warmup_is_separate_and_never_primes_actual_question(tmp_path):
    seen=[]
    def warm(q):seen.append(q);return None,{'embedding':{'call_count':1},'query_text':q}
    event=prepare_warm_query(warm,tmp_path,'D',1,50)
    assert seen==[PROBE]
    assert event['status']=='success' and event['included_in_qa_metrics'] is False
    assert event['question_query_cache_primed'] is False and event['snapshot_load_ms']==50
    assert not list(tmp_path.glob('method_*.jsonl'))
    saved=json.loads((tmp_path/'retrieval_warmup.jsonl').read_text())
    assert saved['warmup_ms']>=0 and saved['request_end']>=saved['request_start']

def test_warmup_failure_cannot_be_reported_as_warm(tmp_path):
    def fail(q):raise RuntimeError('offline')
    with pytest.raises(RuntimeError):prepare_warm_query(fail,tmp_path,'B',1,0)
    assert json.loads((tmp_path/'retrieval_warmup.jsonl').read_text())['status']=='failed'
