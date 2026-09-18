import hashlib
import json
from pathlib import Path
import pickle
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from event_plan import make_plan
from bench_common import read,digest
from online_benchmark import checkpoint,resume,freeze,METHODS
from answer_stream import answer

class ClockTests(unittest.TestCase):
    def test_five_minute_checkpoint_cadence(self):
        plan=make_plan([dict(start_s=0,end_s=901,path='video')],[])
        self.assertEqual([e['end_s'] for e in plan if e['snapshot_due']],[300,600,900])
        with tempfile.TemporaryDirectory(dir=ROOT) as d:
            folder=Path(d);graphs={m:types.SimpleNamespace(method=m) for m in METHODS}
            checkpoint(folder,graphs,1,'config','plan',media_timestamp=17)
            pending=folder/read(folder/'CURRENT.json')['generation']
            checkpoint(folder,graphs,10,'config','plan',media_timestamp=300)
            self.assertFalse(pending.exists())
            first=[folder/r['path'] for r in read(folder/'CURRENT.json')['graphs'].values()]
            checkpoint(folder,graphs,11,'config','plan',media_timestamp=317)
            self.assertTrue(all(p.exists() for p in first))
            self.assertEqual(len(list(folder.rglob('graph.pkl'))),4)
    def test_boundaries_and_no_future(self):
        records=[dict(start_s=0,end_s=1800,path='first'),dict(start_s=1800,end_s=7200,path='second')]
        q=[dict(question_id='a',media_timestamp=3600),dict(question_id='b',media_timestamp=3600),dict(question_id='c',media_timestamp=1234.56789)]
        plan=make_plan(records,q,[dict(start_s=5,end_s=9,source_id='enroll')])
        self.assertEqual([e['end_s'] for e in plan if e['consolidate']],[1200,2400,3600,4800,6000,7200])
        self.assertEqual([e['end_s'] for e in plan if e['compress']],[3600,7200])
        self.assertEqual(len(next(e for e in plan if e['end_s']==3600)['questions']),2)
        for e in plan:
            if e['source']:self.assertLessEqual(e['end_s'],e['source']['end_s'])
            if e['questions']:self.assertTrue(all(q['media_timestamp']==e['end_s'] for q in e['questions']))
            if max(5,e['start_s'])<min(9,e['end_s']):self.assertEqual(e['gap'],'held_out_tst')
        self.assertEqual(digest(plan),digest(make_plan(records,q,[dict(start_s=5,end_s=9,source_id='enroll')])))
    def test_separate_checkpoint_resume_and_refusal(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as d:
            p=Path(d);graphs={m:types.SimpleNamespace(nodes={},segment_times={},method=m) for m in METHODS}
            self.assertEqual(len({id(g) for g in graphs.values()}),4)
            checkpoint(p,graphs,1,'config','plan');loaded,index=resume(p,'config','plan')
            self.assertEqual(index,1);self.assertEqual({g.method for g in loaded.values()},set(METHODS))
            for item in read(p/'CURRENT.json')['graphs'].values():self.assertTrue((p/item['path']).exists())
            for config,plan in [('changed','plan'),('config','changed')]:
                with self.assertRaises(ValueError):resume(p,config,plan)
    def test_snapshot_hash_identity_and_future_refusal(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as d:
            p=Path(d)/'graph.pkl';node=types.SimpleNamespace(type='episodic',metadata={'timestamp':1})
            g=types.SimpleNamespace(nodes={0:node},segment_times={1:(0,12)})
            h=freeze(g,p,12);self.assertEqual(h,hashlib.sha256(p.read_bytes()).hexdigest())
            r1=pickle.loads(p.read_bytes());r2=pickle.loads(p.read_bytes());self.assertIsNot(r1,r2)
            with self.assertRaises(ValueError):freeze(g,Path(d)/'future.pkl',11)

class StreamingTests(unittest.TestCase):
    def test_ttft_is_nonempty_text_delta_exactly_one_call(self):
        calls=[]
        completed=types.SimpleNamespace(model_dump=lambda **kw:dict(id='r',model='gpt-5.6-terra',status='completed',usage={'input_tokens':2,'output_tokens':3,'output_tokens_details':{'reasoning_tokens':1}}))
        events=[types.SimpleNamespace(type='response.created',response=types.SimpleNamespace(id='r')),
            types.SimpleNamespace(type='response.reasoning_summary_text.delta',delta='thinking'),
            types.SimpleNamespace(type='response.output_text.delta',delta=''),
            types.SimpleNamespace(type='response.output_text.delta',delta='A'),types.SimpleNamespace(type='response.completed',response=completed)]
        def create(**kw):calls.append(kw);return iter(events)
        client=types.SimpleNamespace(responses=types.SimpleNamespace(create=create))
        with tempfile.TemporaryDirectory(dir=ROOT) as d:
            q=dict(question='test',query_timestamp=12);r=answer(q,[],Path(d),client)
            self.assertEqual(r['answer'],'A');self.assertEqual(r['answer_calls'],1);self.assertEqual(len(calls),1)
            self.assertEqual(calls[0]['reasoning'],{'effort':'medium'});self.assertTrue(calls[0]['stream'])
            self.assertGreaterEqual(r['generation_complete_ms'],r['ttft_ms'])
            self.assertEqual(r['ttft_event'],'first_nonempty_response.output_text.delta')
            answer(q,[],Path(d),client);self.assertEqual(len(calls),1)
    def test_incomplete_answer_is_not_retried(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as d:
            p=Path(d);(p/'request.json').write_text('{}')
            with self.assertRaises(RuntimeError):answer(dict(question='q',query_timestamp=1),[],p,None)

if __name__=='__main__':unittest.main()

class BoundaryOrderTests(unittest.TestCase):
    def test_real_driver_action_order(self):
        from event_plan import maintenance_actions
        actions=maintenance_actions(dict(consolidate=True,compress=True,questions=[{'id':'q'}]))
        ranks={'consolidate':0,'compress':1,'persist':2,'qa':3}
        self.assertEqual([ranks[x[0]] for x in actions],sorted(ranks[x[0]] for x in actions))
        self.assertEqual([m for a,m in actions if a=='qa'],list(METHODS))
        self.assertEqual([m for a,m in actions if a=='consolidate'],['C3','C4'])
        self.assertEqual([METHODS[m][1] for a,m in actions if a=='compress'],[.5,.5,.5,.7])

class GPUEnvironmentTests(unittest.TestCase):
    def setUp(self):
        import importlib.util
        if not importlib.util.find_spec('torch'):self.skipTest('requires remote main venv')
        from runtime_support import environment
        environment()
    def test_compression_actual_ratios_and_graph_isolation(self):
        from mmagent.videograph import VideoGraph
        from streammeco import compress_graph
        from bench_common import read
        import copy
        graph=VideoGraph(**read(ROOT/'configs/memory_config.json'))
        voice=graph.add_voice_node(dict(embeddings=[],contents=['speaker']))
        for i in range(10):
            node=VideoGraph.Node(i+1,'episodic');node.embeddings=[[1.,float(i+1)]];node.metadata=dict(contents=[f'event {i}'],timestamp=1)
            graph.nodes[i+1]=node;graph.text_nodes.append(i+1);graph.edges[(voice,i+1)]=1
        graph.text_nodes_by_clip={1:list(range(1,11))}
        graph.reference_character_mappings={str(i):dict(node_id=i) for i in range(1,11)}
        a=copy.deepcopy(graph);b=copy.deepcopy(graph)
        a,_=compress_graph(a,retain_ratio=.5);b,_=compress_graph(b,retain_ratio=.7)
        self.assertEqual(len(a.text_nodes),5);self.assertEqual(len(b.text_nodes),7);self.assertEqual(len(graph.text_nodes),10)
        self.assertTrue(all(r['node_id'] in a.nodes for r in a.reference_character_mappings.values()))
    def test_tst_native_online_create_match_update_without_enrollment(self):
        from mmagent.tst_mapper import TSTVoiceMapper
        from mmagent.videograph import VideoGraph
        from bench_common import read
        import numpy as np,base64,io,wave,copy
        buf=io.BytesIO()
        with wave.open(buf,'wb') as w:w.setparams((1,2,16000,0,'NONE','not compressed'));w.writeframes(b'\0\0'*32000)
        data=base64.b64encode(buf.getvalue());mapper=TSTVoiceMapper.__new__(TSTVoiceMapper)
        with tempfile.TemporaryDirectory(dir=ROOT) as d:
            mapper.root=Path(d);mapper.config=dict(threshold=.6,max_audio_embeddings=20,method_id='test',encoder_fingerprint='test_encoder')
            u=np.zeros(192);u[0]=1.;v=np.zeros(192);v[1]=1.
            mapper.extractor=types.SimpleNamespace(extract=lambda x:(np.array([u]),False,1.))
            graph=VideoGraph(**read(ROOT/'configs/memory_config.json'))
            a,ma=mapper.map(graph,data,'one');b,mb=mapper.map(graph,data,'two')
            self.assertEqual(a,b);self.assertTrue(ma['created_new_identity']);self.assertFalse(mb['created_new_identity'])
            self.assertEqual(len(graph.nodes[a].embeddings),2)
            mapper.extractor=types.SimpleNamespace(extract=lambda x:(np.array([v]),True,0.))
            c,mc=mapper.map(graph,data,'three');self.assertNotEqual(a,c);self.assertTrue(mc['created_new_identity'])
            restored=pickle.loads(pickle.dumps(graph));d,md=mapper.map(restored,data,'four');self.assertEqual(c,d)
            self.assertTrue(all(n.metadata['embedding_space']=='speechbrain_ecapa_192' for n in graph.nodes.values()))
            self.assertEqual(graph.search_voice_nodes({'embeddings':[u.tolist()]})[0][0],a)
    def test_voice_injection_never_calls_cam_for_tst(self):
        from mmagent.voice_processing import process_voices
        from mmagent.videograph import VideoGraph
        from bench_common import read
        import base64,io,wave
        buf=io.BytesIO()
        with wave.open(buf,'wb') as w:w.setparams((1,2,16000,0,'NONE','not compressed'));w.writeframes(b'\0\0'*48000)
        audio=base64.b64encode(buf.getvalue());prepared=({'deepgram-asr':[dict(start_time='00:00',end_time='00:03',asr='hello')]},[],{'deepgram-asr':1},1)
        graph=VideoGraph(**read(ROOT/'configs/memory_config.json'))
        def mapped(g,a,t):return g.add_voice_node(dict(embeddings=[],contents=[t])),dict(method_id='test')
        graph.speaker_mapper=types.SimpleNamespace(map=mapped)
        with tempfile.TemporaryDirectory(dir=ROOT) as d, patch('mmagent.voice_processing.get_audio_embeddings',side_effect=AssertionError('CAM invoked')):
            metrics={};process_voices(graph,audio,b'',save_path=str(Path(d)/'voices.json'),metrics=metrics,prepared_asr=prepared)
            self.assertEqual(metrics['speaker_mapping'],'TST');self.assertEqual(metrics['voice_identity_count'],1)

class QueryTransactionTests(unittest.TestCase):
    def test_shared_snapshot_one_build_one_retrieval_one_answer_per_path(self):
        import online_benchmark as driver
        from bench_common import atomic,sha
        import time
        counts={'build':0,'R1':0,'R2':0,'answer':0}
        def native(graph,q,current,**kwargs):
            counts['R1']+=1;return {'CLIP_1':['evidence']},[],{}
        def export(snapshot,folder,**kwargs):
            atomic(folder/'manifest.json',dict(source_graph_sha256=sha(snapshot)))
        class Worker:
            def __init__(self,folder):counts['build']+=1;self.folder=folder
            def search(self,q):
                counts['R2']+=1;return dict(snapshot_sha256=read(self.folder/'mandol_request.json')['snapshot_sha256'],retrieval_calls=1,evidence=['evidence'],retrieval_ms=1)
            def close(self):pass
        def final(q,evidence,out):
            counts['answer']+=1;t=time.time()
            return dict(answer='A',first_content_token_ts=t,response_end_ts=t,ttft_ms=1,generation_complete_ms=1,after_first_token_ms=0)
        modules={'mmagent.retrieve':types.SimpleNamespace(search=native),'m3_agent.export_mandol':types.SimpleNamespace(export_graph=export),'answer_stream':types.SimpleNamespace(answer=final)}
        with tempfile.TemporaryDirectory(dir=ROOT) as d,patch.dict(sys.modules,modules),patch.object(driver,'MandolWorker',Worker):
            graph=types.SimpleNamespace(nodes={},segment_times={})
            event=dict(end_s=1200,questions=[dict(question_id=str(i),question='q',query_timestamp=1200,ground_truth='A') for i in range(2)])
            driver.queries(graph,event,Path(d),'fixture','C1')
            self.assertEqual(counts,{'build':1,'R1':2,'R2':2,'answer':4})
            results=[read(p) for p in Path(d).glob('snapshots/*/answers/*/*/result.json')]
            self.assertEqual(len(results),4);self.assertEqual(len({r['snapshot_sha256'] for r in results}),1)

class FailureTests(unittest.TestCase):
    def test_shared_evidence_preserves_scores_and_moss_source_offsets(self):
        from runtime_support import collect_evidence
        from bench_common import atomic,rows
        view=types.ModuleType('mmagent.clip_audit');view.graph_view=lambda g:dict(nodes=[])
        graph=types.SimpleNamespace(nodes={})
        snapshot=types.SimpleNamespace(graph=graph,cutoff_clip_id=2,cutoff_timestamp=12,graph_version=2)
        plan=[dict(clip_id=1,start_s=5,end_s=10,gap=None,
                   source=dict(path='/source.mp4',start_s=0,source_offset_s=7)),
              dict(clip_id=2,start_s=10,end_s=12,gap='source_gap',source=None)]
        with tempfile.TemporaryDirectory(dir=ROOT) as d,patch.dict(sys.modules,{'mmagent.clip_audit':view}):
            directory=Path(d)
            atomic(directory/'audits/clip_1_audit.json',dict(voice_observations=[dict(
                source_row_index=3,start_time='00:00',end_time='00:02',voice_node_id=4,asr='hello',
                assignment_scores=dict(candidate_scores={'voice_4':.8123456789},threshold=.6,
                                       created_new_identity=False,method_id='ecapa'))]))
            result=collect_evidence(snapshot,directory,'session',plan)
            replay=result['replay'];assignment=rows(result['assignment_jsonl'])[0]
            self.assertEqual(replay['segments'][0]['start_seconds_in_source'],12)
            self.assertEqual(replay['segments'][0]['source'],'/source.mp4')
            self.assertEqual(replay['segments'][1]['gap'],'source_gap')
            self.assertEqual(assignment['candidates'][0]['score'],.8123456789)
            self.assertEqual(assignment['utterance_id'],'session/utt_000001_0003')
            self.assertEqual(assignment['available_at'],7)

    def test_scheduled_consolidation_errors_fail_closed(self):
        from runtime_support import barrier
        def failed(*args,**kwargs):raise RuntimeError('scheduled consolidation failed')
        runtime=types.SimpleNamespace(consolidate_until=failed)
        with tempfile.TemporaryDirectory(dir=ROOT) as d:
            with self.assertRaisesRegex(RuntimeError,'scheduled consolidation failed'):barrier(runtime,1200,Path(d))
    def test_config_change_refuses_resume_before_any_event(self):
        from online_benchmark import source_fingerprint
        before=source_fingerprint()
        self.assertIn('configs/run_request.json',before)
        self.assertIn('source/StreamMeCo/mmagent/voice_processing.py',before)
        self.assertIn('scripts/online_benchmark.py',before)

class MediaBoundaryTests(unittest.TestCase):
    def test_container_tail_is_explicit_gap_and_qa_uses_committed_prefix(self):
        plan=make_plan([dict(start_s=0,end_s=1.024,video_end_s=1.0,path='recording')],[dict(question_id='tail',media_timestamp=1.01)])
        self.assertEqual(plan[0]['end_s'],1.)
        question_event=next(e for e in plan if e['questions'])
        self.assertEqual(question_event['gap'],'audio_container_tail_without_video')
        self.assertEqual(question_event['end_s'],1.01)
        self.assertTrue(all(e['end_s']<=1 for e in plan if not e['gap']))

class MandolTimingReportTests(unittest.TestCase):
    def test_build_is_a_separate_once_per_snapshot_category(self):
        from reports import write_hour
        from bench_common import atomic,jsonl
        with tempfile.TemporaryDirectory(dir=ROOT) as d:
            directory=Path(d);folder=directory/'hour_01';folder.mkdir()
            graph=types.SimpleNamespace(nodes={},edges={},character_mappings={},text_nodes_by_clip={})
            jsonl(directory/'construction.jsonl',[dict(benchmark_timestamp=1200,latency_ms={})])
            snapshot=directory/'snapshots/t_1200'
            atomic(snapshot/'snapshot.json',dict(media_timestamp=1200))
            atomic(snapshot/'mandol_build.json',dict(build_ms=99,dense_embedding_ms=12))
            atomic(snapshot/'mandol_request.json',dict(export_ms=3))
            atomic(snapshot/'mandol_initialization.json',dict(index_reload_and_warmup_ms=10))
            write_hour(graph,dict(end_s=3600),directory,folder,'fixture','C1',{})
            text=(folder/'latency.md').read_text()
            self.assertIn('Mandol adapter/index construction',text)
            self.assertIn('Adapter and index build total | 1 | 99.00',text)
            self.assertIn('excluded from warm retrieval',text)

class RerankTransportTests(unittest.TestCase):
    def test_302_reranker_orders_scores_and_rejects_incomplete_results(self):
        import importlib.util
        if not importlib.util.find_spec('httpx'):self.skipTest('requires remote httpx')
        spec=importlib.util.spec_from_file_location('tested_reranker',ROOT/'source/Mandol/src/mandol/adapters/m3/rerank_302.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        reranker=module.Reranker302.__new__(module.Reranker302)
        reranker.config=dict(endpoint='https://api.302.ai/v1/rerank',model='Qwen/Qwen3-Reranker-0.6B')
        calls=[];body={'results':[dict(index=0,relevance_score=.2),dict(index=1,relevance_score=.9)]}
        def post(url,json):
            calls.append((url,json));return types.SimpleNamespace(raise_for_status=lambda:None,json=lambda:body)
        reranker.client=types.SimpleNamespace(post=post)
        units=[(types.SimpleNamespace(uid=str(i),raw_data={'text_content':f'doc{i}'},text_cached=f'doc{i}'),.5) for i in range(2)]
        ranked,metrics=reranker.rerank('question',units)
        self.assertEqual([u.uid for u,s in ranked],['1','0']);self.assertEqual(len(calls),1)
        self.assertEqual(metrics['endpoint'],'https://api.302.ai/v1/rerank');self.assertEqual(metrics['calls'],1)
        body['results']=[dict(index=0,relevance_score=.2)]
        with self.assertRaises(ValueError):reranker.rerank('question',units)
