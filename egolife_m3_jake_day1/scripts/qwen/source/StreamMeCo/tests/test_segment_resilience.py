import importlib.util
from pathlib import Path
from types import SimpleNamespace
import json
import httpx
import pytest
spec=importlib.util.spec_from_file_location('segment_resilience',Path(__file__).parents[1]/'benchmarks/segment_resilience.py')
r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)

def test_failed_api_rolls_back_then_next_segment_commits(tmp_path):
    graph=SimpleNamespace(nodes={1:'existing'},edges=[])
    def failure():
        graph.nodes[2]='partial';graph.edges.append((1,2))
        raise httpx.ReadTimeout('cloud timeout')
    result=r.transactional_segment(graph,failure,{'segment_id':7},tmp_path)
    assert result['status']=='skipped_api_failure'
    assert graph.nodes=={1:'existing'} and graph.edges==[]
    def success():graph.nodes[3]='next';return {'segment_id':8}
    assert r.transactional_segment(graph,success,{'segment_id':8},tmp_path)['status']=='committed'
    assert graph.nodes=={1:'existing',3:'next'}
    assert len((tmp_path/'api_failures.jsonl').read_text().splitlines())==1

def test_programming_errors_are_not_hidden(tmp_path):
    graph=SimpleNamespace(nodes={})
    def failure():graph.nodes[1]='partial';raise KeyError('bug')
    with pytest.raises(KeyError):r.transactional_segment(graph,failure,{},tmp_path)
    assert graph.nodes=={}
