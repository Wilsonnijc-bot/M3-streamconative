"""Materialize selected source crops, freeze enrollment, independently calibrate ECAPA.

Jake uses accepted recall identities, never QA. AEA labels are manifest-defined
wearer hypotheses verified by cross-recording acoustics, not personal names.
All selected intervals are withheld from subsequent benchmark observations.
"""
import argparse
import base64
from collections import defaultdict
import io
import math
import os
from pathlib import Path
import subprocess
import sys
import wave
from bench_common import REPOSITORY_ROOT, ROOT, REVISION, atomic, read, rows, jsonl, sha, digest
sys.path.insert(0, str(REPOSITORY_ROOT))


def jake(repo):
    folder = ROOT / 'tst_assets/jake'; (folder / 'audio').mkdir(parents=True, exist_ok=True)
    pub = repo / 'consolidation/runs/recall_20/round_1/published/session_37ddbff70718d62b0d3a'
    version = pub / 'versions' / read(pub / 'CURRENT.json')['version']
    patch = read(version / 'patch.json')
    views = read(version / 'views.json')
    graph = read(version / 'graph.json')
    excluded = {u for d in patch['decisions'] for u in d.get('excluded_utterance_ids', [])}
    groups = defaultdict(list)
    for view in views:
        obs = view['historical']; ident = view['consolidated'].get('entity_id')
        meta = graph['assignment_metadata'].get(obs['utterance_id'], {})
        duration = obs['end_time'] - obs['start_time']
        if ident in {'person_0','person_1','person_2','person_3'} and obs['utterance_id'] not in excluded and duration >= 3 and meta.get('confidence',0) >= .79:
            groups[ident].append((meta['confidence'], duration, obs))
    selected = []; used_clips = set()
    # Globally disjoint clips, deterministic longest high-confidence candidates.
    for ident in sorted(groups, key=lambda g: (len(groups[g]), g)):
        picked = []
        for confidence, duration, obs in sorted(groups[ident], key=lambda v:(-v[1],-v[0],v[2]['utterance_id'])):
            if obs['clip_id'] in used_clips: continue
            cache_ref, fragment = obs['audio_ref'].split('#')
            cache = repo / 'egolife_m3_jake_day1/cache/voices/gemini/work/intermediate' / Path(cache_ref).name
            item = read(cache)[int(fragment.split('/')[2])]
            data = base64.b64decode(item['audio_segment'])
            with wave.open(io.BytesIO(data)) as wav:
                actual = wav.getnframes() / wav.getframerate()
            filename = ident + '_' + obs['utterance_id'].split('/')[-1] + '.wav'
            path = folder / 'audio' / filename; atomic(path,data,True)
            role = 'enrollment' if len(picked) < 2 else 'calibration'
            row = dict(global_speaker_id=ident, role=role, source_id=obs['utterance_id'],
                recording_id='jake_clip_' + str(obs['clip_id']), audio_path=str(path.relative_to(ROOT)),
                start_s=0., end_s=actual, sha256=sha(path),
                benchmark_start_s=obs['start_time'], benchmark_end_s=obs['end_time'],
                verification_provenance=dict(kind='accepted_recall_round1', confidence=confidence,
                    observation=obs, decision=meta, patch_sha256=sha(version/'patch.json'),
                    cache_sha256=sha(cache), accepted_version=version.name))
            picked.append(row); used_clips.add(obs['clip_id'])
            if len(picked)==4: break
        if len(picked)<4: raise ValueError(f'insufficient disjoint accepted Jake speech for {ident}: {len(picked)}')
        selected.extend(picked)
    if len(groups)!=4: raise ValueError('missing Jake identities')
    jsonl(folder/'candidates.jsonl', selected)
    atomic(folder/'provenance.json',dict(patch_sha256=sha(version/'patch.json'),
        views_sha256=sha(version/'views.json'), observations_sha256=sha(pub/'observations.jsonl'),
        excluded_utterance_ids=sorted(excluded), selection='confidence >= .79, duration >=3s, sort confidence/duration/ID; 2 enroll + 2 calibrate, globally disjoint clips'))
    print('JAKE_CROPS',len(selected),flush=True)


def aea(media):
    import numpy as np
    import soundfile as sf
    from tst.scoring import matrix, score
    folder=ROOT/'tst_assets/aea'; (folder/'audio').mkdir(parents=True,exist_ok=True)
    manifest=read(media/'aea_6h_manifest.json')
    from runtime_support import environment
    environment()
    from mmagent.utils.chat_api import transcribe_audio_with_retry
    encoder, extractor = load_encoder()
    selected=[]; candidate_audit=[]
    asr_cache=folder/'speech_checks';asr_cache.mkdir(exist_ok=True)
    # Candidates from distinct scripts without consulting QA content; full recording decoded to RAM only.
    for loc in range(1,6):
        by_script=defaultdict(list)
        for r in manifest['recordings']:
            if r['location']==loc and r['rec']==1 and not r['alternate_wearer']:
                by_script[r['script']].append(r)
        pools=[]
        for script, recordings in sorted(by_script.items()):
            pool=[]
            for rec in recordings:
                data=subprocess.check_output(['ffmpeg','-v','error','-i',str(media/rec['video_path']),'-vn','-ac','1','-ar','16000','-f','f32le','pipe:1'])
                wave=np.frombuffer(data,dtype='<f4')
                candidates=[]
                for start in range(2,max(2,int(len(wave)/16000)-6),6):
                    chunk=wave[start*16000:(start+6)*16000]
                    rms=float(np.sqrt(np.mean(chunk**2)))
                    activity=float(np.mean(np.sqrt(np.mean(chunk.reshape(-1,320)**2,axis=1))>.003))
                    if rms>=.002 and activity>=.25 and float(np.mean(np.abs(chunk)>.99))<.02:
                        candidates.append((rms,start,chunk))
                if loc == 5:
                    # Sparse-speech fallback: scan the complete source recording so
                    # loud non-speech windows cannot crowd out quieter utterances.
                    full_path=asr_cache/(rec['sequence_id']+'_full.json')
                    if full_path.exists(): full_speech=read(full_path)
                    else:
                        buffer=io.BytesIO();sf.write(buffer,wave,16000,format='WAV',subtype='PCM_16')
                        full_speech=transcribe_audio_with_retry('deepgram-asr',buffer.getvalue(),audio_format='wav')
                        atomic(full_path,full_speech)
                    def stamp(t):
                        a,b=map(float,t.split(':'));return 60*a+b
                    starts=sorted({max(0,min(int(stamp(x['start_time'])),int(len(wave)/16000)-6)) for x in full_speech if len(x['asr'].split())>=4})
                    candidates=[]
                    for start in starts:
                        chunk=wave[start*16000:(start+6)*16000];rms=float(np.sqrt(np.mean(chunk**2)))
                        if len(chunk)==96000 and rms>=.001:candidates.append((rms,start,chunk))
                for rms,start,chunk in sorted(candidates,key=lambda x:(-x[0],x[1]))[:5]:
                    name=f"{rec['sequence_id']}_{start}.wav"; path=folder/'audio'/name
                    sf.write(path,chunk,16000,subtype='PCM_16')
                    check_path=asr_cache/(sha(path)+'.json')
                    if check_path.exists(): speech=read(check_path)
                    else:
                        speech=transcribe_audio_with_retry('deepgram-asr',path.read_bytes(),audio_format='wav')
                        atomic(check_path,speech)
                    def stime(t):
                        a,b=map(float,t.split(':'));return 60*a+b
                    if not speech or len({x.get('speaker') for x in speech})!=1 or sum(len(x['asr'].split()) for x in speech)<4 or max(stime(x['end_time']) for x in speech)-min(stime(x['start_time']) for x in speech)<3:
                        path.unlink();continue
                    row=dict(global_speaker_id=f'aea_loc{loc}_rec1',source_id=name,recording_id=rec['sequence_id'],script=script,
                        audio_path=str(path.relative_to(ROOT)),start_s=0.,end_s=6.,sha256=sha(path),
                        benchmark_start_s=round(rec['global_start_s']+start,6),benchmark_end_s=round(rec['global_start_s']+start+6,6),
                        verification_provenance=dict(kind='manifest_wearer_acoustic_hypothesis',manifest_sha256=sha(media/'aea_6h_manifest.json'),
                            recording=rec,rms=rms,speech=speech,speech_check_sha256=sha(check_path),claim='Manifest-defined location/rec1 wearer; not independently verified personal identity.'))
                    vector,_,_=extractor.extract(dict(row,audio_path=str(path)))
                    pool.append((row,vector)); candidate_audit.append(row)
            if pool: pools.append((script,pool))
        if len(pools)<2:
            atomic(folder/'partial_selection.json',dict(selected=selected,candidate_audit=candidate_audit,failed_location=loc,available_scripts=[p[0] for p in pools]))
            raise ValueError(f'AEA location {loc} lacks speech in separate scripts')
        # Identity selection is enrollment-side only. Calibration script is held out
        # before selecting an enrollment medoid; no threshold labels tune selection.
        enrollment_pools=[x for x in pools if len({r['recording_id'] for r,v in x[1]})>=2]
        if not enrollment_pools: enrollment_pools=pools  # sparse speech: verify across held-out recording below
        enroll_script,enroll_pool=enrollment_pools[0]
        cal_script,cal_pool=next(x for x in pools if x[0]!=enroll_script)
        best=max(range(len(enroll_pool)),key=lambda i:(sum(score(enroll_pool[i][1],v,'cosine')[0] for j,(r,v) in enumerate(enroll_pool) if r['recording_id']!=enroll_pool[i][0]['recording_id']),-i))
        anchor,anchor_v=enroll_pool[best]
        enroll=[anchor]
        other=[(score(anchor_v,v,'cosine')[0],r) for r,v in enroll_pool if r['recording_id']!=anchor['recording_id']]
        second=max(other,key=lambda x:(x[0],x[1]['source_id'])) if other else (None,None)
        if other:
            if second[0]<.35: raise ValueError(f'AEA {loc} cross-recording enrollment inconsistent: {second[0]}')
            enroll.append(second[1])
        # One high-energy candidate per calibration recording, selected without match score.
        cal=[]
        for r,v in cal_pool:
            if r['recording_id'] not in {x['recording_id'] for x in cal}: cal.append(r)
            if len(cal)==3: break
        if not cal: raise ValueError('AEA missing independent calibration recording')
        for r in enroll: selected.append(dict(r,role='enrollment'))
        for r in cal: selected.append(dict(r,role='calibration'))
        print('AEA_CROPS',loc,'enroll',len(enroll),'cal',len(cal),'within',second[0],flush=True)
    selected_paths={r['audio_path'] for r in selected}
    for r in candidate_audit:
        if r['audio_path'] not in selected_paths: (ROOT/r['audio_path']).unlink(missing_ok=True)
    jsonl(folder/'candidates.jsonl', selected)
    atomic(folder/'candidate_audit.json',dict(candidates=candidate_audit,retained=sorted(selected_paths),
        rule='First script with two speech-verified recordings for enrollment; first different script for calibration. Single diarized speaker and >=4 words required. Enrollment cross-recording medoid; held-out calibration highest-energy speech-active crop per recording.'))


def load_encoder():
    from tst.encoder import SpeechBrainEncoder
    from tst.audio import AudioExtractor
    os.environ['HF_HOME']=str(ROOT/'tst_assets/huggingface')
    encoder=SpeechBrainEncoder(dict(revision=REVISION,device='cuda'),ROOT/'tst_assets/ecapa_model')
    extractor=AudioExtractor(encoder,encoder.fingerprint,ROOT/'tst_assets/ecapa_cache')
    return encoder,extractor


def calibrate(dataset):
    import numpy as np
    from tst.scoring import matrix, score
    from tst.runner import run
    folder=ROOT/'tst_assets'/dataset
    candidates=rows(folder/'candidates.jsonl')
    enrollment=[r for r in candidates if r['role']=='enrollment']; calibration=[r for r in candidates if r['role']=='calibration']
    if {r['recording_id'] for r in enrollment}&{r['recording_id'] for r in calibration}: raise ValueError('recording overlap')
    for i,a in enumerate(candidates):
        for b in candidates[i+1:]:
            if max(a['benchmark_start_s'],b['benchmark_start_s']) < min(a['benchmark_end_s'],b['benchmark_end_s']): raise ValueError('interval overlap')
    jsonl(folder/'enrollment.jsonl',enrollment);jsonl(folder/'calibration.jsonl',calibration)
    encoder,extractor=load_encoder()
    gallery=defaultdict(list)
    for row in enrollment:
        vectors,_,_=extractor.extract(dict(row,audio_path=str(ROOT/row['audio_path'])))
        gallery[row['global_speaker_id']].extend(vectors)
    gallery={g:matrix(v) for g,v in gallery.items()}
    trials=[]; mappings=[]
    for row in calibration:
        vectors,hit,ms=extractor.extract(dict(row,audio_path=str(ROOT/row['audio_path'])))
        scores={g:score(v,vectors,'cosine')[0] for g,v in sorted(gallery.items())}
        mappings.append(dict(source_id=row['source_id'],expected=row['global_speaker_id'],scores=scores))
        for g,value in scores.items(): trials.append(dict(source_id=row['source_id'],target=g,positive=g==row['global_speaker_id'],score=value))
    values=sorted({t['score'] for t in trials}); thresholds=[-1.000001]+[(a+b)/2 for a,b in zip(values,values[1:])]+[1.000001]
    pos=[t['score'] for t in trials if t['positive']]; neg=[t['score'] for t in trials if not t['positive']]
    def metric(th):
        far=sum(s>=th for s in neg)/len(neg);frr=sum(s<th for s in pos)/len(pos)
        return far,frr
    threshold=min(thresholds,key=lambda t:((sum(metric(t))/2),metric(t)[0],-t))
    far,frr=metric(threshold)
    et=min(thresholds,key=lambda t:(abs(metric(t)[0]-metric(t)[1]),sum(metric(t)),-t)); eer=sum(metric(et))/2
    gallery_id=digest(dict(policy='all_enrolled',candidates={},enrollment=sha(folder/'enrollment.jsonl')))
    # tst.runner uses default json separators in its digest; import its exact function.
    from tst.runner import digest as tst_digest
    gallery_id=tst_digest(dict(policy='all_enrolled',candidates={},enrollment=sha(folder/'enrollment.jsonl')))
    method_id=tst_digest(dict(diarization_provider='deepgram-asr',encoder=encoder.fingerprint,normalization='cosine',gallery=gallery_id,cohort=None,
        compensation=dict(mode='none',profile='short4_equal_segment_mean_v1')))
    accuracy=sum(max(r['scores'],key=lambda g:(r['scores'][g],g))==r['expected'] and r['scores'][r['expected']]>=threshold for r in mappings)/len(mappings)
    artifact=dict(method_id=method_id,threshold=threshold,calibration_data_id=sha(folder/'calibration.jsonl'),
        FAR=far,FRR=frr,EER=eer,EER_threshold=et,closed_set_accept_accuracy=accuracy,
        positive_trials=len(pos),negative_trials=len(neg),enrollment_count=len(enrollment),calibration_count=len(calibration),
        optimization='Minimize balanced FAR/FRR on all candidate midpoints; tie lower FAR then higher threshold. EER nearest discrete operating point.',
        limitations='Small development calibration; no independent test error estimate. AEA labels are manifest-defined wearer hypotheses.')
    jsonl(folder/'trials.jsonl',trials);atomic(folder/'threshold.json',artifact);atomic(folder/'calibration_scores.json',mappings)
    atomic(folder/'encoder.json',dict(model='speechbrain/spkrec-ecapa-voxceleb',revision=REVISION,expected_embedding_dim=192,
        fingerprint=encoder.fingerprint,asset_hashes=encoder.asset_hashes,versions=encoder.versions,device='cuda',cache='tst_assets/huggingface'))
    exclusions=[dict(start_s=r['benchmark_start_s'],end_s=r['benchmark_end_s'],source_id=r['source_id'],role=r['role']) for r in candidates]
    atomic(folder/'overlap_audit.json',dict(enrollment_calibration_overlap=False,recording_overlap=False,benchmark_policy='Skip full selected intervals for all C1-C4; add boundaries to event plan.',excluded_intervals=exclusions))
    config=dict(enrollment=str((folder/'enrollment.jsonl').relative_to(ROOT)),calibration=str((folder/'calibration.jsonl').relative_to(ROOT)),
        threshold_artifact=str((folder/'threshold.json').relative_to(ROOT)),encoder_provenance=str((folder/'encoder.json').relative_to(ROOT)),
        threshold=threshold,method_id=method_id,gallery_id=gallery_id,encoder_fingerprint=encoder.fingerprint,
        diarization_provider='deepgram-asr',encoder=dict(model='speechbrain/spkrec-ecapa-voxceleb',revision=REVISION,expected_embedding_dim=192),
        gallery=dict(policy='all_enrolled'),scoring=dict(normalization='cosine',threshold=threshold,threshold_artifact=artifact),
        compensation=dict(mode='none'),excluded_intervals=exclusions,
        manifest_hashes={str(p.relative_to(ROOT)):sha(p) for p in folder.rglob('*') if p.is_file()},
        validation_passed=bool(pos and neg and math.isfinite(threshold)),
        calibration_quality_warning=accuracy<.60 or far>.20 or frr>.40)
    atomic(ROOT/'configs'/f'tst_{dataset}.json',config)
    print(dataset,json_summary(artifact), 'VALID',config['validation_passed'],flush=True)
    if not config['validation_passed']: raise ValueError(dataset+' acoustic calibration failed acceptance gate')


def json_summary(x):
    import json
    return json.dumps(x,sort_keys=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['jake','aea','calibrate']);p.add_argument('--repo',type=Path,default=ROOT.parents[1]);p.add_argument('--media',type=Path,default=Path('/opt/streammeco/aea_6h'));p.add_argument('--dataset',choices=['jake','aea']);a=p.parse_args()
    if a.action=='jake':jake(a.repo)
    elif a.action=='aea':aea(a.media)
    else:calibrate(a.dataset)
