"""Integer-microsecond media clock; half-open crops and explicit source gaps."""
from pathlib import Path
from bench_common import ROOT, read, atomic, sha, digest
import subprocess

SCALE=1_000_000
def tick(seconds): return round(seconds*SCALE)
def seconds(t): return t/SCALE

def make_plan(recordings, questions, exclusions=(), max_segment_s=30):
    end=max(tick(r['end_s']) for r in recordings)
    cuts={0,end}
    cuts.update(range(tick(300),end+1,tick(300)))
    cuts.update(range(tick(1200),end+1,tick(1200)))
    cuts.update(range(tick(3600),end+1,tick(3600)))
    by_time={}
    for q in questions:
        t=tick(q['media_timestamp'])
        if t<0 or t>end:raise ValueError('question outside available stream: '+q['question_id'])
        cuts.add(t);by_time.setdefault(t,[]).append(q)
    for r in recordings:
        cuts.update((tick(r['start_s']),tick(r['end_s'])))
        if 'video_end_s' in r:cuts.add(tick(r['video_end_s']))
        cuts.update(range(tick(r['start_s'])+tick(max_segment_s),tick(r['end_s']),tick(max_segment_s)))
    for r in exclusions:cuts.update((tick(r['start_s']),tick(r['end_s'])))
    cuts=sorted(t for t in cuts if 0<=t<=end)
    plan=[]
    for i,(a,b) in enumerate(zip(cuts,cuts[1:]),1):
        candidates=[r for r in recordings if tick(r['start_s'])<=a and b<=tick(r['end_s'])]
        if len(candidates)>1:raise ValueError('overlapping source recordings')
        excluded=[r for r in exclusions if max(a,tick(r['start_s']))<min(b,tick(r['end_s']))]
        source=candidates[0] if candidates else None
        no_video=source is not None and a>=tick(source.get('video_end_s',source['end_s']))
        plan.append(dict(clip_id=i,start_s=seconds(a),end_s=seconds(b),source=source,
            excluded=excluded,gap='held_out_tst' if excluded else ('source_gap' if source is None else ('audio_container_tail_without_video' if no_video else None)),
            snapshot_due=(b%tick(300)==0),consolidate=(b%tick(1200)==0),compress=(b%tick(3600)==0),
            questions=sorted(by_time.get(b,[]),key=lambda q:q['question_id'])))
    if by_time.get(0):raise ValueError('zero-time QA requires explicit initial state support')
    return plan

def add_video_availability(recordings):
    import json
    for r in recordings:
        info=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=duration','-of','json',r['path']]))
        duration=float(info['streams'][0]['duration'])
        r['video_duration_s']=duration
        r['video_end_s']=round(min(r['end_s'],r['start_s']+duration),6)
        if r['end_s']-r['video_end_s']>1:raise ValueError('Unexpected long audio-only tail; needs explicit audio-only processing')

def prepare_manifests():
    out=ROOT/'configs/media';out.mkdir(parents=True,exist_ok=True)
    for dataset in ('jake','aea'):
        if dataset=='aea':
            base=Path('/opt/streammeco/aea_6h');manifest=base/'aea_6h_manifest.json';raw=read(manifest)
            recordings=[dict(source_id=r['sequence_id'],path=str(base/r['video_path']),start_s=r['global_start_s'],end_s=r['global_end_s'],source_offset_s=0) for r in raw['recordings']]
            origin=0
        else:
            base=Path('/opt/streammeco/data/egolife_day1');files=sorted(list(base.glob('DAY1_A1_JAKE_*.mp4'))+list((ROOT/'media/jake').glob('DAY1_A1_JAKE_*.mp4')),key=lambda p:p.name)
            def clock(p):
                value=p.stem.rsplit('_',1)[-1]
                return int(value[:2])*3600+int(value[2:4])*60+int(value[4:6])+int(value[6:])/100
            origin=clock(files[0]);recordings=[]
            for i,p in enumerate(files):
                duration=float(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','default=noprint_wrappers=1:nokey=1',str(p)]))
                end=clock(p)+duration
                if i+1<len(files):end=min(end,clock(files[i+1]))
                recordings.append(dict(source_id=p.name,path=str(p),start_s=round(clock(p)-origin,6),end_s=round(end-origin,6),source_offset_s=0))
            manifest=None
        add_video_availability(recordings)
        for r in recordings:
            p=Path(r['path']);r['bytes']=p.stat().st_size;r['sha256']=sha(p)
        payload=dict(dataset=dataset,origin_s=origin,recordings=recordings,
            original_manifest_sha256=sha(manifest) if manifest else None)
        atomic(out/f'{dataset}.json',payload)
        print('MEDIA_MANIFEST',dataset,len(recordings),recordings[-1]['end_s'],flush=True)

if __name__=='__main__':prepare_manifests()

def maintenance_actions(event):
    """All methods have already committed this timestamp before these actions."""
    actions=[]
    if event['consolidate']:actions += [('consolidate',m) for m in ('C3','C4')]
    if event['compress']:
        actions += [('compress',m) for m in ('C1','C2','C3','C4')]
        actions += [('persist',m) for m in ('C1','C2','C3','C4')]
    if event['questions']:actions += [('qa',m) for m in ('C1','C2','C3','C4')]
    return actions
