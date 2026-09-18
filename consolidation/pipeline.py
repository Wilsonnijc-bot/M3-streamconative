"""Transactional publication: one CURRENT pointer selects graph and retrieval together."""
import fcntl
import hashlib
import os
import shutil
import tempfile
from copy import deepcopy
from pathlib import Path
from .common import read, write, digest, dumps
from .observations import ObservationLedger
from .entity_registry import initial_state
from .evidence_builder import build_evidence
from .patch_executor import execute
from .canonicalizer import canonicalize
from .retrieval_refresh import refresh, HashEmbedder
from .audit import render


def session_directory(root, session):
    return Path(root)/('session_'+hashlib.sha256(session.encode()).hexdigest()[:20])


def load_current(root, session):
    directory=session_directory(root,session)
    if not (directory/'CURRENT.json').exists():
        return None
    pointer=read(directory/'CURRENT.json')
    version=pointer['version']
    if not version.startswith('v_') or any(c not in 'v_0123456789abcdef' for c in version):
        raise ValueError('invalid version pointer')
    location=directory/'versions'/version
    if (location/'graph.pkl').exists():
        from .native import current_graph, proposal_state
        graph = current_graph(root, session)
        packet = read(location/'evidence.json')
        return proposal_state(graph, session, packet['observations'], version)
    manifest=read(location/'manifest.json')
    for name, expected in manifest['sha256'].items():
        if Path(name).name!=name:
            raise ValueError('invalid manifest path')
        if hashlib.sha256((location/name).read_bytes()).hexdigest()!=expected:
            raise ValueError('version integrity failure: '+name)
    state=read(location/'state.json')
    if state['session_id']!=session or state['graph_version']!=version:
        raise ValueError('published state namespace/version mismatch')
    return state


def prepare(replay, output, moss=None, assignments=(), native_graph=None):
    from .native import current_graph, proposal_state, validate_source
    graph = native_graph or current_graph(output, replay['session_id'])
    if graph is not None:
        validate_source(graph, replay['memories'])
        replay['native_graph'] = graph
        state = proposal_state(graph, replay['session_id'], replay['observations'], replay['source_graph_version'])
        return state, build_evidence(replay, state, moss, assignments)
    current=load_current(output,replay['session_id'])
    state=current or initial_state(replay['session_id'],replay['source_graph_version'])
    packet=build_evidence(replay,state,moss,assignments)
    return state,packet


def publish(replay, output, state, packet, patch, embedder=None, llm_artifacts=None):
    if replay.get('native_graph') is not None:
        from .native import publish_native
        return publish_native(replay, output, state, packet, patch, replay['native_graph'],
                              embedder=embedder, llm_artifacts=llm_artifacts)
    directory=session_directory(output,replay['session_id'])
    directory.mkdir(parents=True,exist_ok=True)
    with (directory/'.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        actual=load_current(output,replay['session_id'])
        if actual and actual['graph_version']!=state['graph_version']:
            raise ValueError('concurrent publication changed the base')
        if actual is None and state['graph_version']!=replay['source_graph_version']:
            raise ValueError('base version no longer exists')
        if state['session_id']!=replay['session_id']:
            raise ValueError('session mismatch')
        new_state,report=execute(state,packet,patch)
        ObservationLedger(directory/'observations.jsonl',replay['session_id']).append(replay['observations'])
        memories=canonicalize(replay['memories'],replay['observations'],new_state)
        retrieval=refresh(memories,new_state,embedder or HashEmbedder())
        graph=deepcopy(replay['graph'])
        graph['canonical_entities']=deepcopy(new_state['entities'])
        graph['utterance_assignments']=deepcopy(new_state['assignments'])
        graph['canonical_memories']=memories
        graph['assignment_metadata']=deepcopy(new_state.get('assignment_metadata',{}))
        graph['cluster_defaults']=deepcopy(new_state.get('cluster_defaults',{}))
        graph['identity_edges']=[dict(source=u,target=e,type='utterance_identity') for u,e in sorted(new_state['assignments'].items())]
        payload=dict(state=new_state,graph=graph,retrieval=retrieval,patch=patch,packet=packet)
        version='v_'+digest(payload)
        new_state['graph_version']=version
        for item in (graph,retrieval):
            item['graph_version']=version
            item['session_id']=replay['session_id']
        versions=directory/'versions'
        versions.mkdir(exist_ok=True)
        staged=Path(tempfile.mkdtemp(prefix='.staged-',dir=versions))
        try:
            for name,value in [('state',new_state),('graph',graph),('retrieval',retrieval),('patch',patch),
                               ('evidence',packet),('execution',report)]:
                write(staged/(name+'.json'),value)
            views=[dict(utterance_id=o['utterance_id'], historical=o,
                consolidated={'entity_id':new_state['assignments'].get(o['utterance_id']),
                    'name':new_state['entities'].get(new_state['assignments'].get(o['utterance_id']),{}).get('canonical_name')})
                for o in replay['observations']]
            write(staged/'views.json',views)
            audit=render(packet,new_state,report,retrieval)
            provenance=read(Path(llm_artifacts)/'llm_metadata.json') if llm_artifacts and (Path(llm_artifacts)/'llm_metadata.json').exists() else {'backend':'direct structured patch; no model invocation recorded'}
            (staged/'audit.md').write_text(audit+'\n## Proposal provenance\n'+dumps(provenance)+'\n')
            if llm_artifacts:
                for name in ('llm_input.json','llm_response.json','llm_output.txt','llm_metadata.json',
                             'prompt_packet.json','prompt_scope.json','prompt_size.json'):
                    source=Path(llm_artifacts)/name
                    if source.exists():
                        shutil.copyfile(source,staged/name)
            manifest={'version':version,'source_graph_version':replay['source_graph_version'],
                'sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in staged.iterdir()}}
            write(staged/'manifest.json',manifest)
            destination=versions/version
            if destination.exists():
                raise ValueError('version already exists')
            os.rename(staged,destination)
            write(directory/'CURRENT.json',{'version':version})
        finally:
            if staged.exists():
                shutil.rmtree(staged)
        return destination, report
