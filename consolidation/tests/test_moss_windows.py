from copy import deepcopy
import io
import shutil
import wave

import pytest

from consolidation.common import read, write
from consolidation.moss_alignment import align, validate_window
from consolidation.moss_runner import prepare_window, normalize_segments, WindowMoss
from consolidation.runtime import ConsolidationSnapshot
from consolidation.runtime_io import NativeConsolidationWorker
from .test_transports import server
from .test_native_characters import graph, publication_inputs


def test_local_runner_gap_window_never_invents_speech(tmp_path):
    from consolidation.moss_local import LocalWindowMoss
    replay=dict(session_id='s',origin_seconds=0,current_cutoff=2400,
                segments=[dict(absolute_start_seconds=1200,absolute_end_seconds=2400,gap='source_gap')])
    runner=LocalWindowMoss('unused','revision','unused',python='must-not-be-called')
    result=runner(replay,1200,tmp_path/'gap')
    assert result['segments']==[] and result['model_called'] is False
    assert runner(replay,1200,tmp_path/'gap')==result
    with pytest.raises(ValueError,match='input changed'):
        runner(replay,0,tmp_path/'gap')


def test_local_runner_preserves_recorded_audio_and_labels_missing_tail(tmp_path,monkeypatch):
    import subprocess
    from consolidation.moss_local import LocalWindowMoss
    replay=dict(session_id='s',origin_seconds=0,current_cutoff=1200,segments=[
        dict(absolute_start_seconds=0,absolute_end_seconds=18,source='recorded_silence.wav'),
        dict(absolute_start_seconds=18,absolute_end_seconds=1200,gap='source_gap')])
    def run(command,**kwargs):
        manifest=read(tmp_path/'job/window.json')
        assert manifest['current_cutoff']==18
        assert len(manifest['segments'])==1
        write(tmp_path/'job/results/window/moss.json',dict(session_id='s',start_s=0,cutoff_s=18,
            timestamp_origin='session',run_id='r',segments=[]))
    monkeypatch.setattr(subprocess,'run',run)
    value=LocalWindowMoss('checkpoint','revision','repository')(replay,0,tmp_path/'job')
    assert value['cutoff_s']==1200 and value['inference_cutoff_s']==18
    assert value['unobserved_tail']==[18,1200]
    assert read(tmp_path/'job/results/window/moss.json')['cutoff_s']==18


def audio_source(tmp_path):
    if not shutil.which('ffmpeg'):
        pytest.skip('ffmpeg unavailable')
    path=tmp_path/'source.wav'
    with wave.open(str(path),'wb') as w:
        w.setnchannels(1);w.setsampwidth(2);w.setframerate(16000)
        w.writeframes(b'\x01\x00'*16000 + b'\x02\x00'*16000 + b'\x03\x00'*16000)
    return dict(session_id='s',origin_seconds=100,current_cutoff=3,segments=[dict(
        absolute_start_seconds=100,absolute_end_seconds=103,start_seconds_in_source=0,source='source.wav')])


def pcm(path):
    with wave.open(str(path),'rb') as w:
        return w.getnframes(),w.readframes(w.getnframes())


def test_window_crops_source_offsets_and_keeps_only_requested_audio(tmp_path):
    replay=audio_source(tmp_path)
    replay['current_cutoff']=2.5
    path=prepare_window(replay,tmp_path,tmp_path/'window.wav',1.5)
    count,samples=pcm(path)
    assert count==16000
    assert samples==b'\x02\x00'*8000+b'\x03\x00'*8000


def test_window_gaps_and_short_final_tail(tmp_path):
    replay=audio_source(tmp_path)
    replay['segments']=[dict(absolute_start_seconds=101,absolute_end_seconds=102,
                            start_seconds_in_source=1,source='source.wav')]
    path=prepare_window(replay,tmp_path,tmp_path/'window.wav',.5)
    count,samples=pcm(path)
    assert count==40000
    assert samples==b'\0\0'*8000+b'\x02\x00'*16000+b'\0\0'*16000
    replay['current_cutoff']=1.25
    count,samples=pcm(prepare_window(replay,tmp_path,tmp_path/'tail.wav',1))
    assert count==4000 and samples==b'\x02\x00'*4000


@pytest.mark.parametrize('start',[0,1200,2400])
def test_twenty_minute_windows_normalize_once_and_keep_speakers_run_local(start):
    segments=normalize_segments([dict(start=0,end=1200,speaker='S01',text='speech')],start,start+1200)
    moss=dict(session_id='s',start_s=start,cutoff_s=start+1200,timestamp_origin='session',
              run_id=f'run_{start}',segments=segments)
    observations=[dict(utterance_id='new',original_voice_id='voice_0',start_time=start,end_time=start+1)]
    if start:
        observations.append(dict(utterance_id='old',original_voice_id='voice_0',start_time=0,end_time=1))
    records,_,_=align(observations,moss,'s',start+1200,start)
    assert len(records)==1 and records[0]['speaker']==f'run_{start}/S01'
    assert segments[0]['start']==start and segments[0]['end']==start+1200
    with pytest.raises(ValueError):
        normalize_segments([dict(start=1199,end=1201,speaker='S01',text='future')],start,start+1200)


def test_rejects_full_prefix_wrong_session_wrong_origin_and_old_segments():
    valid=dict(session_id='s',start_s=1200,cutoff_s=2400,timestamp_origin='session',run_id='r',
               segments=[dict(start=1200,end=1201,speaker='S01',text='new')])
    for changes in (dict(start_s=0),dict(session_id='other'),dict(cutoff_s=3600),
                    dict(timestamp_origin='window'),dict(segments=[dict(start=0,end=1,speaker='S01')])):
        with pytest.raises(ValueError):
            validate_window(dict(valid,**changes),'s',1200,2400)


def test_http_window_audio_timestamp_offset_and_cache(server,tmp_path):
    endpoint,requests=server
    replay=audio_source(tmp_path);replay['current_cutoff']=2
    runner=WindowMoss(endpoint,tmp_path,revision='test')
    result=runner(replay,1,tmp_path/'job')
    assert pcm(tmp_path/'job/window.wav')==(16000,b'\x02\x00'*16000)
    assert result['segments']==[dict(start=1,end=2,speaker='S01',text='Hi')]
    assert result['start_s']==1 and result['cutoff_s']==2 and result['timestamp_origin']=='session'
    assert read(tmp_path/'job/model_input.json')['timestamp_origin']=='window'
    wire=requests[0][1]
    with wave.open(io.BytesIO(wire[wire.index(b'RIFF'):]),'rb') as w:
        assert w.getnframes()==16000
    assert runner(replay,1,tmp_path/'job')==result
    assert len(requests)==1
    with pytest.raises(ValueError,match='window mismatch'):
        runner(replay,0,tmp_path/'job')
    assert len(requests)==1
    assert pcm(tmp_path/'job/window.wav')==(16000,b'\x02\x00'*16000)


def test_worker_runs_moss_before_reasoning_at_each_committed_boundary(tmp_path):
    g=graph()
    replay,_,_,_=publication_inputs(g)
    replay['memories']=[dict(m,available_at=1200) for m in replay['memories']]
    calls=[]
    def moss(replay,start,directory):
        calls.append(('moss',start,replay['current_cutoff']))
        return dict(session_id='s',start_s=start,cutoff_s=replay['current_cutoff'],
            timestamp_origin='session',run_id='window_'+str(start),segments=[
                dict(start=start,end=start+1,speaker='S01',text='new speech')])
    def propose(packet,directory):
        calls.append(('reason',packet['previous_cutoff'],packet['current_cutoff']))
        uids=packet['_execution_scope']['new_observation_ids']
        voices=sorted({o['original_voice_id'] for o in packet['observations'] if o['utterance_id'] in uids})
        return dict(schema_version=1,session_id='s',base_graph_version=packet['base_graph_version'],
            evidence_cutoff_s=packet['current_cutoff'],decisions=[dict(op='assign_cluster',decision_id='new',
                voice_ids=voices,target_entity_id='person_0',evidence_ids=[uids[0]],confidence=.9,
                rationale='Returning speaker.',excluded_utterance_ids=[])])
    from consolidation.port import make_worker
    worker=make_worker(lambda s:dict(replay=deepcopy(replay)),propose,tmp_path,moss=moss)
    for n in (1,2,3):
        if n>1:
            g.update_node(0,dict(contents=['new'],embeddings=[[1.,0.,0.]]))
            replay['observations'].append(dict(utterance_id='u'+str(n+1),original_voice_id='voice_0',
                clip_id=n,session_id='s',start_time=(n-1)*1200,end_time=(n-1)*1200+1))
        replay['current_cutoff']=n*1200
        g=worker(ConsolidationSnapshot(n,n,n*1200,g)).graph
    assert calls==[(kind,start,start+1200) for start in (0,1200,2400) for kind in ('moss','reason')]
    assert g.identity_cutoff==3600 and g.identity_cutoff_clip==3
    assert read(tmp_path/'snapshot_3/phase_timings.json')['worker_wall_ms']>0


def test_worker_moss_failure_and_mismatch_never_call_reasoner(tmp_path,monkeypatch):
    g=graph();replay,_,_,_=publication_inputs(g)
    monkeypatch.delenv('MOSS_ENDPOINT',raising=False)
    monkeypatch.delenv('MOSS_MEDIA_ROOT',raising=False)
    def forbidden(*args): pytest.fail('reasoner ran without valid MOSS')
    def failed(*args): raise RuntimeError('MOSS unavailable')
    worker=NativeConsolidationWorker(lambda s:dict(replay=replay),forbidden,tmp_path,moss=failed)
    with pytest.raises(RuntimeError,match='MOSS unavailable'):
        worker(ConsolidationSnapshot(1,1,10,g))
    worker.moss=None
    with pytest.raises(ValueError,match='configure a MOSS'):
        worker(ConsolidationSnapshot(1,1,10,g))
    worker.moss=lambda *args:dict(session_id='s',start_s=1,cutoff_s=10,run_id='bad',segments=[])
    with pytest.raises(ValueError,match='window mismatch'):
        worker(ConsolidationSnapshot(1,1,10,g))
    assert g.identity_revision==0


def test_local_manifest_sequence_uses_previous_committed_end(tmp_path):
    from consolidation.moss_local import manifest_windows
    paths=[]
    for cutoff in (1187.92,2387.92,3587.92):
        path=tmp_path/f'{cutoff}.json'
        write(path,dict(session_id='s',current_cutoff=cutoff))
        paths.append(path)
    assert [(start,replay['current_cutoff']) for _,replay,start in manifest_windows(paths)]==[
        (0,1187.92),(1187.92,2387.92),(2387.92,3587.92)]
    assert next(manifest_windows(paths[1:2],1187.92))[2]==1187.92
    write(paths[1],dict(session_id='s',previous_cutoff=0,current_cutoff=2387.92))
    with pytest.raises(ValueError,match='consecutive windows'):
        list(manifest_windows(paths))


def test_live_cli_runs_moss_for_native_window_before_proposal(tmp_path,monkeypatch):
    import sys
    from types import SimpleNamespace
    from consolidation import __main__ as cli, native
    from .test_prompt_packet import history_packet
    replay,state,packet=history_packet(2)
    calls=[]
    class Runner:
        def __init__(self,endpoint,media_root,**kwargs):
            assert endpoint=='http://moss/v1'
        def __call__(self,replay,start,directory):
            assert start==1200 and replay['current_cutoff']==2400
            calls.append('moss')
            return packet['moss']
    monkeypatch.setattr(cli,'WindowMoss',Runner)
    monkeypatch.setattr(cli,'load_replay',lambda *args:replay)
    monkeypatch.setattr(native,'load_graph',lambda path:SimpleNamespace(identity_cutoff=1200))
    def prepare(*args,**kwargs):
        assert args[2]['start_s']==1200
        calls.append('prepare')
        return state,packet
    monkeypatch.setattr(cli,'prepare',prepare)
    def propose(*args,**kwargs):
        calls.append('reason')
        return {}
    monkeypatch.setattr(cli,'propose',propose)
    def publish(*args,**kwargs):
        calls.append('publish')
        return tmp_path,dict(accepted=[],rejected=[])
    monkeypatch.setattr(cli,'publish',publish)
    monkeypatch.setattr(sys,'argv',['consolidation','run','--cutoff','2400','--native-graph','graph.pkl',
        '--work',str(tmp_path),'--model','test','--endpoint','http://model/v1',
        '--moss-endpoint','http://moss/v1','--media-root',str(tmp_path)])
    cli.main()
    assert calls==['moss','prepare','reason','publish']
    assert read(tmp_path/'prompt_packet.json')['moss']['start_s']==1200
