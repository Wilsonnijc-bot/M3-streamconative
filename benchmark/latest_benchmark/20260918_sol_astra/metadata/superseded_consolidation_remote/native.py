"""Bridge accepted consolidation conclusions into the current native M3 graph."""
from copy import deepcopy
from pathlib import Path
import hashlib
import importlib
import os
import pickle
import re
import sys

from .common import read, write, digest
from .entity_registry import initial_state, refresh_registry


def m3_module(name):
    if name in sys.modules:
        return sys.modules[name]
    root = Path(__file__).resolve().parents[1] / 'StreamMeCo'
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    previous = Path.cwd()
    try:
        os.chdir(root)
        return importlib.import_module(name)
    finally:
        os.chdir(previous)


def load_graph(path):
    module = m3_module('mmagent.videograph')
    sys.modules.setdefault('videograph', module)
    with Path(path).open('rb') as handle:
        return pickle.load(handle)


def current_graph(root, session):
    from .pipeline import session_directory
    directory = session_directory(root, session)
    if not (directory / 'CURRENT.json').exists():
        return None
    version = read(directory / 'CURRENT.json')['version']
    if not re.fullmatch(r'v_[0-9a-f]{64}', version):
        raise ValueError('invalid native graph version pointer')
    location = directory / 'versions' / version
    if not (location / 'graph.pkl').exists():
        return None
    for name, expected in read(location / 'manifest.json')['sha256'].items():
        if (Path(name).is_absolute() or '..' in Path(name).parts
                or not (location / name).is_file()
                or hashlib.sha256((location / name).read_bytes()).hexdigest() != expected):
            raise ValueError('native version integrity failure')
    graph = load_graph(location / 'graph.pkl')
    if graph.graph_version != version or graph.identity_session != session:
        raise ValueError('native graph session/version mismatch')
    return graph


def proposal_state(graph, session, observations, source_version):
    """Rebuild transient proposal aliases from native characters, never audit state."""
    identity = m3_module('mmagent.character_identity')
    identity.initialize(graph)
    state = initial_state(session, getattr(graph, 'graph_version', source_version))
    state['cutoff'] = getattr(graph, 'identity_cutoff', 0)
    state['consolidation_index'] = getattr(graph, 'identity_revision', 0)
    aliases = {c: 'person_' + c.split('_')[-1] for c in graph.character_mappings}
    for character, alias in aliases.items():
        metadata = graph.character_metadata.get(character, {})
        state['entities'][alias] = dict(native_character_id=character, voice_ids=[], utterance_ids=[],
            canonical_name=metadata.get('canonical_name'), aliases=metadata.get('aliases', []),
            name_evidence=metadata.get('name_evidence', metadata.get('evidence_ids', [])),
            created_at_consolidation=0, updated_at_consolidation=state['consolidation_index'])
    for observation in observations:
        uid = observation['utterance_id']
        character = graph.observation_character_mappings.get(uid)
        if character:
            state['assignments'][uid] = aliases[character]
    for key, reference in graph.reference_character_mappings.items():
        state['references'][key] = dict(memory_node_id=str(reference['node_id']),
            mention=reference['mention'], entity_id=aliases[reference['character_id']],
            evidence_ids=reference['evidence_ids'], content_index=reference['content_index'],
            start=reference['start'], end=reference['end'])
    state['claims'] = deepcopy(getattr(graph, 'memory_claim_revisions', {}))
    state['cannot_link'] = [[aliases.get(key, key) for key in pair]
                            for pair in getattr(graph, 'character_constraints', [])]
    state['assignment_metadata'] = {uid: deepcopy(record) for uid, record in graph.identity_observations.items()
                                    if uid in state['assignments']}
    refresh_registry(state, observations)
    for character, alias in aliases.items():
        features = graph.character_mappings[character]
        entity = state['entities'][alias]
        entity['voice_ids'] = sorted(set(entity['voice_ids']) | {f for f in features if f.startswith('voice_')})
        entity['face_ids'] = sorted(f for f in features if f.startswith('face_'))
    return state


def validate_source(graph, memories):
    for memory in memories:
        node = graph.nodes.get(int(memory['memory_node_id']))
        if node is None or node.type != memory['kind'] or '\n'.join(node.metadata['contents']) != memory['raw_text']:
            raise ValueError('native graph differs from reviewed memories; supply the native construction graph for this prefix')


def project(graph, state, packet):
    identity = m3_module('mmagent.character_identity')
    if getattr(graph, 'identity_session', packet['session_id']) != packet['session_id']:
        raise ValueError('native graph belongs to a different session')
    validate_source(graph, packet['memories'])
    if any(o.get('end_time', 0) > packet['current_cutoff'] for o in packet['observations']):
        raise ValueError('observation lies after the publication cutoff')
    observations = []
    for item in packet['observations']:
        uid = item['utterance_id']
        metadata = state.get('assignment_metadata', {}).get(uid, {})
        observations.append(dict(observation_id=uid,
            feature_id=item.get('original_feature_id', item.get('original_face_id', item.get('original_voice_id'))),
            entity_id=state['assignments'].get(uid), raw_text=item.get('original_transcript'),
            evidence_ids=metadata.get('evidence_ids', []), confidence=metadata.get('confidence'),
            rationale=metadata.get('rationale'),
            candidate_feature_ids=item.get('original_assignment_evidence', {}).get('candidate_voice_ids', [])))
    provenance = dict(session_id=packet['session_id'], base_graph_version=packet['base_graph_version'],
        evidence_cutoff_s=packet['current_cutoff'], reviewed_memory_ids=[m['memory_node_id'] for m in packet['memories']])
    relevant = set(state['assignments'].values()) | {r['entity_id'] for r in state['references'].values()}
    if state['decision_history']:
        relevant.update(d['entity_id'] for d in state['decision_history'][-1]['accepted'] if d['op'] == 'set_name')
    conclusions = {key: value for key, value in state['entities'].items() if key in relevant}
    report = identity.apply_conclusions(graph, conclusions, observations,
        list(state['references'].values()), cutoff=packet['current_cutoff'], provenance=provenance)
    graph.identity_session = packet['session_id']
    graph.identity_cutoff_clip = max([o.get('clip_id', 0) for o in packet['observations']] + [0])
    graph.memory_claim_revisions = deepcopy(state['claims'])
    graph.character_constraints = [[report['conclusion_characters'].get(key,
        state['entities'].get(key, {}).get('native_character_id', key)) for key in pair]
        for pair in state['cannot_link']]
    return report


def publish_native(replay, output, state, packet, patch, graph, embedder=None,
                   llm_artifacts=None, resolved_state=None, execution=None):
    import fcntl
    import shutil
    import tempfile
    from .pipeline import session_directory
    from .patch_executor import execute
    from . import reindex_cycle
    deployment = reindex_cycle.deployment_config()
    identity = m3_module('mmagent.character_identity')
    directory = session_directory(output, replay['session_id'])
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / '.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        current = current_graph(output, replay['session_id'])
        if current is not None and current.graph_version != packet['base_graph_version']:
            raise ValueError('concurrent publication changed native base')
        if current is None and (directory / 'CURRENT.json').exists():
            raise ValueError('cannot overlay a non-native publication; use a new version root')
        if getattr(graph, 'graph_version', packet['base_graph_version']) != packet['base_graph_version']:
            raise ValueError('supplied native graph has a stale base')
        new_state, report = (resolved_state, execution) if resolved_state is not None else execute(state, packet, patch)
        staged_graph = deepcopy(graph)
        identity_report = project(staged_graph, new_state, packet)
        embedding_report = identity.reindex_text(staged_graph, embedder.encode if embedder else None)
        # The index is the existing native text-node embeddings, not a second vector store.
        version = 'v_' + digest(dict(base=packet['base_graph_version'], state=new_state, deployment=deployment,
                                    identity=identity_report, embedding=embedding_report,
                                    native_graph_sha256=hashlib.sha256(pickle.dumps(
                                        staged_graph, protocol=pickle.HIGHEST_PROTOCOL)).hexdigest(),
                                    text_vectors={str(n.id): n.embeddings for n in staged_graph.nodes.values()
                                                  if n.type in ('semantic', 'episodic')}))
        staged_graph.graph_version = version
        versions = directory / 'versions'
        versions.mkdir(exist_ok=True)
        staged = Path(tempfile.mkdtemp(prefix='.staged-', dir=versions))
        try:
            with (staged / 'graph.pkl').open('wb') as handle:
                pickle.dump(staged_graph, handle, protocol=pickle.HIGHEST_PROTOCOL)
            view = m3_module('mmagent.videograph_markdown').graph_view(staged_graph)
            write(staged / 'graph.json', view)
            for name, value in [('proposal_audit', new_state), ('evidence', packet), ('patch', patch),
                                ('execution', report), ('identity_changes', identity_report),
                                ('embedding_manifest', embedding_report)]:
                write(staged / (name + '.json'), value)
            if llm_artifacts:
                for name in ('llm_input.json', 'llm_output.txt', 'llm_response.json', 'llm_metadata.json'):
                    source = Path(llm_artifacts) / name
                    if source.exists():
                        shutil.copyfile(source, staged / name)
            mandol = reindex_cycle.build_retrieval_bundle(staged, staged_graph, deployment)
            if mandol.get('status') != 'ready' or mandol.get('graph_version') != version:
                raise ValueError('retrieval bundle is not ready for publication')
            write(staged/'retrieval_ready.json', dict(status='ready', graph_version=version,
                native_graph='graph.pkl', mandol_graph='mandol', mandol=mandol))
            write(staged / 'manifest.json', dict(version=version, native_character_state=True,
                retrieval_complete=True,
                sha256={str(p.relative_to(staged)): hashlib.sha256(p.read_bytes()).hexdigest()
                        for p in staged.rglob('*') if p.is_file()}))
            destination = versions / version
            os.rename(staged, destination)
            write(directory / 'CURRENT.json', {'version': version})
        except Exception:
            if (staged/'mandol_build.log').exists():
                shutil.copyfile(staged/'mandol_build.log', directory/'last_reindex_failure.log')
            raise
        finally:
            if staged.exists():
                shutil.rmtree(staged)
        return destination, report
