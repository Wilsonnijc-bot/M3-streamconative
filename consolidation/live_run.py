"""Run real MOSS-backed checkpoints through the configured official GPT-6 Astra."""
import argparse
import os
from pathlib import Path
from .common import read,write
from .replay import load_replay
from .pipeline import prepare,publish,load_current
from .llm_consolidator import propose_official


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--minutes',type=int,required=True)
    parser.add_argument('--output',default='consolidation/runs/live')
    parser.add_argument('--api-config',default='StreamMeCo/configs/api_config.json')
    parser.add_argument('--native-graph', help='native M3 pickle required for initial publication')
    parser.add_argument('--moss-json',help='precomputed MOSS output for exactly this native-state window')
    parser.add_argument('--moss-endpoint',default=os.environ.get('MOSS_ENDPOINT'))
    parser.add_argument('--media-root',default=os.environ.get('MOSS_MEDIA_ROOT'))
    parser.add_argument('--moss-revision',default=os.environ.get('MOSS_REVISION','server-unspecified'))
    args=parser.parse_args()
    root=Path(args.output)
    if args.minutes<=0:
        parser.error('--minutes must be positive')
    replay=load_replay('egolife_m3_jake_day1','egolife_m3_jake_day1/gemini',args.minutes*60)
    from .native import load_graph, current_graph
    native = load_graph(args.native_graph) if args.native_graph else current_graph(root/'published', replay['session_id'])
    if native is None:
        parser.error('provide --native-graph for the first native consolidation')
    work=root/'metadata'/f'astra_{args.minutes}'
    if args.moss_json:
        moss=read(args.moss_json)
    elif args.moss_endpoint and args.media_root:
        from .moss_runner import WindowMoss
        moss=WindowMoss(args.moss_endpoint,args.media_root,revision=args.moss_revision)(
            replay,getattr(native,'identity_cutoff',0),work/'moss')
    else:
        parser.error('configure --moss-endpoint and --media-root or supply exact-window --moss-json')
    state,packet=prepare(replay,root/'published',moss,native_graph=native)
    write(work/'evidence.json',packet)
    print('ASTRA_BEGIN',args.minutes,'observations',len(packet['observations']),
        'MOSS_segments',len(moss['segments']),flush=True)
    patch=propose_official(packet,work,args.api_config)
    print('ASTRA_COMPLETED',args.minutes,'decisions',len(patch['decisions']),flush=True)
    destination,report=publish(replay,root/'published',state,packet,patch,llm_artifacts=work)
    final=load_current(root/'published',replay['session_id'])
    summary={'minutes':args.minutes,'cutoff_s':packet['current_cutoff'],'version':destination.name,
        'path':str(destination),'accepted':len(report['accepted']),'rejected':len(report['rejected']),
        'entities':len(final['entities']),'assigned_observations':len(final['assignments']),
        'names':{eid:e['canonical_name'] for eid,e in final['entities'].items() if e['canonical_name']},
        'moss_segments':len(moss['segments']),'moss_speakers':len({s['speaker'] for s in moss['segments']})}
    write(root/f'checkpoint_{args.minutes}.json',summary)
    print('CONSOLIDATION_COMPLETE',summary,flush=True)


if __name__=='__main__':main()
