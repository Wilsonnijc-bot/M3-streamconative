"""Bind planned intervals to actual video-track availability, preserving source clock."""
from bench_common import ROOT,read,atomic
from event_plan import add_video_availability

if __name__=='__main__':
    for dataset in ('jake','aea'):
        path=ROOT/'configs/media'/f'{dataset}.json';manifest=read(path)
        add_video_availability(manifest['recordings']);atomic(path,manifest)
        gaps=[dict(source_id=r['source_id'],video_end_s=r['video_end_s'],container_end_s=r['end_s']) for r in manifest['recordings'] if r['video_end_s']<r['end_s']]
        atomic(ROOT/'metadata'/f'{dataset}_video_availability.json',dict(container_tail_gaps=gaps))
        print('VIDEO_AVAILABILITY',dataset,'explicit tiny container tails',len(gaps),flush=True)
