import argparse
import os
from pathlib import Path
from .common import read,write
from .replay import load_replay
from .pipeline import prepare,publish
from .llm_consolidator import propose,request_payload
from .moss_runner import WindowMoss


def main():
    p=argparse.ArgumentParser(description='Offline M3 entity consolidation')
    p.add_argument('command',choices=['prepare','run','moss'])
    p.add_argument('--root',default='egolife_m3_jake_day1')
    p.add_argument('--session',default='egolife_m3_jake_day1/gemini')
    p.add_argument('--cutoff',type=float,required=True,help='requested elapsed seconds')
    p.add_argument('--metadata',help='override M3 source-segment metadata JSON')
    p.add_argument('--output',default='consolidation/runs')
    p.add_argument('--work',required=True,help='exact evidence/request/response run directory')
    p.add_argument('--moss-json')
    p.add_argument('--native-graph', help='native M3 pickle for first publication; later runs use CURRENT')
    p.add_argument('--assignment-jsonl')
    p.add_argument('--patch',help='recorded structured patch JSON (no live LLM)')
    p.add_argument('--model',default='recorded-patch')
    p.add_argument('--endpoint',help='chat API base URL ending /v1')
    p.add_argument('--embedding-model',help='SentenceTransformer model; default is explicit local hash baseline')
    p.add_argument('--embedding-endpoint',help='use an embeddings API instead of SentenceTransformer')
    p.add_argument('--media-root',default=os.environ.get('MOSS_MEDIA_ROOT'))
    p.add_argument('--moss-endpoint',default=os.environ.get('MOSS_ENDPOINT'))
    p.add_argument('--moss-revision',default=os.environ.get('MOSS_REVISION','server-unspecified'))
    p.add_argument('--start-s',type=float,help='standalone moss window start; run derives it from native state')
    a=p.parse_args()
    replay=load_replay(a.root,a.session,a.cutoff,a.metadata)
    work=Path(a.work); work.mkdir(parents=True,exist_ok=True)
    from .native import load_graph, current_graph
    native = load_graph(a.native_graph) if a.native_graph else current_graph(a.output, a.session)
    start = getattr(native,'identity_cutoff',0)
    if a.start_s is not None:
        if a.command!='moss' or (native is not None and abs(a.start_s-start)>1e-6):
            p.error('--start-s is only for standalone moss and must match supplied native state')
        start=a.start_s
    if a.command=='moss':
        if not a.media_root or not a.moss_endpoint:
            p.error('moss requires --media-root and --moss-endpoint')
        WindowMoss(a.moss_endpoint,a.media_root,revision=a.moss_revision)(replay,start,work)
        return
    moss=read(a.moss_json) if a.moss_json else None
    import json
    assignments=[json.loads(line) for line in Path(a.assignment_jsonl).read_text().splitlines()] if a.assignment_jsonl else []
    if native is None:
        p.error('native consolidation requires --native-graph for its first publication')
    if a.command=='run':
        if not a.patch and (not a.endpoint or a.model=='recorded-patch'):
            p.error('run requires --patch or both --endpoint and --model')
        if moss is None and a.moss_endpoint and a.media_root:
            moss=WindowMoss(a.moss_endpoint,a.media_root,revision=a.moss_revision)(replay,start,work/'moss')
        if moss is None and not a.patch:
            p.error('live run requires --moss-json or configured --moss-endpoint and --media-root')
    state,packet=prepare(replay,a.output,moss,assignments,native_graph=native)
    write(work/'evidence.json',packet)
    write(work/'llm_input.json',request_payload(packet,a.model,work))
    if a.command=='prepare':
        print(f"Prepared {len(packet['observations'])} observations and {len(packet['memories'])} memories at {packet['current_cutoff']}s")
        return
    patch=propose(packet,work,a.model,a.endpoint,patch_file=a.patch)
    if a.embedding_endpoint and not a.embedding_model:
        p.error('--embedding-endpoint requires --embedding-model')
    if a.embedding_endpoint or a.embedding_model:
        p.error('native publication uses the configured M3 text embedding backend')
    destination,report=publish(replay,a.output,state,packet,patch,llm_artifacts=work)
    print(f"Published {destination}: {len(report['accepted'])} accepted, {len(report['rejected'])} rejected")


if __name__=='__main__':
    main()
