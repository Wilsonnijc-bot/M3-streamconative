"""Adapters for the existing evidence, Astra, native application and index cycle."""
from copy import deepcopy
import hashlib
import os
from pathlib import Path
import pickle
import shutil
import tempfile
import time

from .common import write
from .runtime import ConsolidationPatch


class NativeConsolidationWorker:
    """evidence(snapshot) supplies the existing replay/MOSS/assignment records.

    propose(packet, directory) is the existing configured Astra callable (or a
    saved-decision callable for tests). No prompt or decision policy changes.
    """
    def __init__(self, evidence, propose, directory):
        self.evidence, self.propose = evidence, propose
        self.directory = Path(directory)

    def __call__(self, snapshot):
        from .native import proposal_state, project, validate_source
        from .evidence_builder import build_evidence
        from .patch_executor import execute
        started = time.perf_counter(); phase = {}
        inputs = self.evidence(snapshot)
        phase['evidence_collection_ms'] = (time.perf_counter()-started)*1000
        stage = time.perf_counter()
        replay = inputs['replay']
        if replay['current_cutoff'] != snapshot.cutoff_timestamp:
            raise ValueError('evidence cutoff differs from frozen snapshot')
        if any(o['clip_id'] > snapshot.cutoff_clip_id or o['end_time'] > snapshot.cutoff_timestamp
               for o in replay['observations']):
            raise ValueError('evidence includes observations after snapshot cutoff')
        validate_source(snapshot.graph, replay['memories'])
        state = proposal_state(snapshot.graph, replay['session_id'], replay['observations'],
                               replay['source_graph_version'])
        packet = build_evidence(replay, state, inputs.get('moss'), inputs.get('assignments', ()))
        directory = self.directory / ('snapshot_' + str(snapshot.graph_version))
        directory.mkdir(parents=True, exist_ok=True)
        with (directory/'snapshot.pkl').open('wb') as handle:
            pickle.dump(snapshot.graph, handle, protocol=pickle.HIGHEST_PROTOCOL)
        write(directory/'snapshot.json', dict(graph_version=snapshot.graph_version,
            cutoff_clip_id=snapshot.cutoff_clip_id, cutoff_timestamp=snapshot.cutoff_timestamp))
        write(directory/'evidence.json', packet)
        phase['snapshot_evidence_preparation_ms'] = (time.perf_counter()-stage)*1000
        stage = time.perf_counter()
        patch = self.propose(packet, directory)
        phase['llm_request_parse_ms'] = (time.perf_counter()-stage)*1000
        stage = time.perf_counter()
        state, execution = execute(state, packet, patch)
        write(directory/'patch.json', patch)
        write(directory/'execution.json', execution)
        if execution.get('rejected') and not execution.get('accepted'):
            raise ValueError('all proposed consolidation decisions were rejected')
        phase['patch_execution_ms'] = (time.perf_counter()-stage)*1000
        stage = time.perf_counter()
        result = deepcopy(snapshot.graph)
        report = project(result, state, packet)
        write(directory/'patch.json', patch)
        write(directory/'execution.json', execution)
        write(directory/'identity_changes.json', report)
        phase['identity_resolution_staging_ms'] = (time.perf_counter()-stage)*1000
        phase['worker_wall_ms'] = (time.perf_counter()-started)*1000
        write(directory/'phase_timings.json', phase)
        return ConsolidationPatch(snapshot, result)


class RetrievalPublisher:
    """Background native + Mandol publication after the runtime's native reindex.

    The live graph is never replaced by this historical retrieval checkpoint.
    """
    def __init__(self, directory):
        self.directory = Path(directory)

    def __call__(self, graph):
        import fcntl
        from .common import read
        from .reindex_cycle import build_retrieval_bundle, deployment_config
        directory = self.directory
        directory.mkdir(parents=True, exist_ok=True)
        versions = directory/'versions'
        versions.mkdir(exist_ok=True)
        # This is a publication lock, unrelated to the live graph writer.
        with (directory/'.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            pointer = directory/'CURRENT.json'
            if pointer.exists():
                previous = read(versions/read(pointer)['version']/'runtime.json')
                if previous['current_graph_version'] >= graph.current_graph_version:
                    raise ValueError('stale runtime retrieval publication')
            config = deployment_config()
            for node in graph.nodes.values():
                node.metadata.pop('embedding_stale', None)
            graph.graph_version = 'v_' + hashlib.sha256(pickle.dumps(graph)).hexdigest()
            staged = Path(tempfile.mkdtemp(prefix='.staged-', dir=versions))
            try:
                with (staged/'graph.pkl').open('wb') as handle:
                    pickle.dump(graph, handle, protocol=pickle.HIGHEST_PROTOCOL)
                write(staged/'runtime.json', {key: getattr(graph, key) for key in (
                    'current_graph_version', 'last_consolidated_clip_id',
                    'last_consolidated_timestamp', 'entity_registry_version')})
                mandol = build_retrieval_bundle(staged, graph, config)
                if mandol.get('status') != 'ready' or mandol.get('graph_version') != graph.graph_version:
                    raise ValueError('retrieval bundle is not ready for this runtime version')
                write(staged/'retrieval_ready.json', dict(status='ready', graph_version=graph.graph_version,
                    native_graph='graph.pkl', mandol_graph='mandol', mandol=mandol))
                write(staged/'manifest.json', dict(version=graph.graph_version, retrieval_complete=True,
                    sha256={str(p.relative_to(staged)): hashlib.sha256(p.read_bytes()).hexdigest()
                            for p in staged.rglob('*') if p.is_file()}))
                os.rename(staged, versions/graph.graph_version)
                write(pointer, {'version': graph.graph_version})
            finally:
                if staged.exists():
                    if (staged/'mandol_build.log').exists():
                        shutil.copyfile(staged/'mandol_build.log', directory/'last_reindex_failure.log')
                    shutil.rmtree(staged)
