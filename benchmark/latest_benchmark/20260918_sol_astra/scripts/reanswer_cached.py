"""Explicit future backend comparison using saved question/evidence pairs, no GPU rebuild."""
import argparse
from pathlib import Path
import time
from bench_common import ROOT,atomic,read,sha
import answer_stream


def main():
    p=argparse.ArgumentParser();p.add_argument('--model',required=True);p.add_argument('--input',type=Path,default=ROOT/'results');p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    output=a.output.resolve()
    if not output.is_relative_to(ROOT):raise ValueError('reanswer output must remain in isolated benchmark folder')
    answer_stream.MODEL=a.model
    count=0
    for path in sorted(a.input.glob('*/C*/snapshots/*/answers/*/R*/result.json')):
        original=read(path);relative=path.relative_to(a.input).parent
        result=answer_stream.answer(original['question'],original['retrieval']['evidence'],output/relative)
        atomic(output/relative/'replay.json',dict(source_result=str(path),source_result_sha256=sha(path),
            snapshot_sha256=original['snapshot_sha256'],cached_evidence=True,new_retrieval_calls=0,
            timing_scope='new streamed final-answer call only; original retrieval/construction are cached',answer=result))
        count+=1
    atomic(output/'COMPLETE.json',dict(model=a.model,count=count,completed_at=time.time()))
    print('CACHED_REANSWER_COMPLETE',count,flush=True)

if __name__=='__main__':main()
