import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import pytest

spec=importlib.util.spec_from_file_location('gemini_report_test',Path(__file__).parents[1]/'benchmarks/gemini_report.py')
r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)

def dump(p,value):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(value))

def test_full_report_and_lineage_guard(tmp_path):
    root=tmp_path
    (root/'mandol').mkdir()
    gemini={'model':'gemini-3.8-flash','returned_model':'gemini-3.8-flash','latency_ms':10}
    for i in range(1,11):
        native=root/'memory'/f'q{i:02d}_uncompressed'/'graph.pkl';native.parent.mkdir(parents=True);native.write_bytes(f'graph{i}'.encode())
        h=hashlib.sha256(native.read_bytes()).hexdigest()
        dump(native.with_name('metadata.json'),{'source_segments':[{'absolute_end_seconds':i}],'query_time_seconds':i})
        compressed=root/'streammeco_compressed'/f'q{i:02d}'/'graph.pkl';compressed.parent.mkdir(parents=True);compressed.write_bytes(f'compressed{i}'.encode())
        ch=hashlib.sha256(compressed.read_bytes()).hexdigest()
        dump(compressed.with_name('metadata.json'),{'source_graph_sha256':h})
        d=root/'mandol_adapted'/f'q{i:02d}'
        dump(d/'mapping_m3_to_mandol.json',{'1':'m3_1'})
        dump(d/'interchange'/'manifest.json',{'source_graph_sha256':h})
        for method,name in r.NAMES.items():
            event={'embedding':{'total_ms':2},'retrieval':{'TOTAL_RETRIEVAL_MS':5,'warm_engine':True,'dense_ms':1,'backend_calls':[{'method':m} for m in ['bm25','cosine_similarity','splade']]}}
            x={'latency_mode':'warm_retrieval_uncached_question','question_index':i,'question':{'id':str(i)},'memory':{'nodes':3},'retrieval_rounds':[event],
               'controller_calls':[gemini] if method=='A' else [],'final_answer_call':gemini,
               'retrieval_round_count':1,'FULL_QUESTION_TO_ANSWER_MS':15,'prediction':'A','correct':True,
               'evaluated_graph_sha256':ch if method=='C' else h}
            with (root/name).open('a') as f:f.write(json.dumps(x)+'\n')
    for name in ['gemini_calls.jsonl','memory_construction_latency.jsonl','compression_metrics.json']:
        (root/name).write_text(json.dumps(gemini)+'\n')
    args=SimpleNamespace(results=root)
    r.report(args);r.validate(args)
    assert json.loads((root/'validation.json').read_text())['qa_rows']==40
    assert len((root/'comparison.csv').read_text().splitlines())==41
    assert set(json.loads((root/'aggregate_metrics.json').read_text()))==set('ABCD')
    native.write_bytes(b'changed')
    with pytest.raises(RuntimeError,match='lineage mismatch'):r.validate(args)
