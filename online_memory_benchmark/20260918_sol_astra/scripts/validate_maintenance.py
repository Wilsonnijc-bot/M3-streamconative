"""Real Sol/native maintenance on GPU-prefix graphs with explicitly synthetic gaps.

No later media is read. This is an integration smoke, not a one-hour data result.
"""
import argparse
import copy
from pathlib import Path
import pickle
import sys
from bench_common import ROOT,read,atomic,append
from runtime_support import environment

def main():
    p=argparse.ArgumentParser();p.add_argument('--prefix',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    environment()
    a.prefix=a.prefix.resolve();a.output=a.output.resolve()
    from runtime_support import attach,barrier
    from online_benchmark import METHODS,hourly
    from streammeco import compress_graph
    source=a.prefix/'jake';state=read(source/'CURRENT.json');full_plan=read(source/'event_plan.json');plan=full_plan[:state['event_index']]
    last=plan[-1]['end_s'];index=plan[-1]['clip_id']
    for cutoff in (1200,2400,3600):
        index+=1;plan.append(dict(clip_id=index,start_s=last,end_s=cutoff,gap='diagnostic_missing_media',source=None,excluded=[],consolidate=True,compress=cutoff==3600,questions=[]));last=cutoff
    for method in ('C3','C4'):
        directory=a.output/method;directory.mkdir(parents=True,exist_ok=True)
        # Audits refer to the actual processed prefix; all later intervals are explicit gaps.
        (directory/'audits').symlink_to(source/method/'audits',target_is_directory=True)
        (directory/'intermediate').symlink_to(source/method/'intermediate',target_is_directory=True)
        g=pickle.loads((source/state['graphs'][method]['path']).read_bytes())
        runtime=attach(g,directory,f'jake/{method}',plan)
        try:
            for e in plan[state['event_index']:]:
                with runtime.segment(e['clip_id'],e['end_s']):g.segment_times[e['clip_id']]=(e['start_s'],e['end_s'])
                result=barrier(runtime,e['end_s'],directory)
                if e['compress']:
                    before=sum(n.type in ('episodic','semantic') for n in g.nodes.values())
                    g,summary=compress_graph(g,retain_ratio=METHODS[method][1])
                    after=sum(n.type in ('episodic','semantic') for n in g.nodes.values())
                    compression=dict(before=before,after=after,requested_ratio=METHODS[method][1],actual_retention=after/before if before else None,summary=summary)
                    # Copy raw records for report generation; the synthetic gaps are labeled.
                    original=(source/method/'construction.jsonl').read_bytes()
                    atomic(directory/'construction.jsonl',original,True)
                    hourly(g,e,directory,'jake',method,compression)
        finally:runtime.close()
    atomic(a.output/'PASS.json',dict(status='passed',mode='GPU-prefix + synthetic missing-media clock',cutoffs=[1200,2400,3600],constructions=['C3','C4']))
    print('MAINTENANCE_SMOKE_PASS',flush=True)

if __name__=='__main__':main()
