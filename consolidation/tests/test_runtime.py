from copy import deepcopy
import pickle
import threading
import time

import pytest

from consolidation.native import m3_module
from consolidation.runtime import ConsolidationRuntime, ConsolidationPatch, reconcile

identity = m3_module('mmagent.character_identity')
VideoGraph = m3_module('mmagent.videograph').VideoGraph


def graph():
    g = VideoGraph()
    for text in ('a', 'b'):
        g.add_voice_node(dict(contents=[text], embeddings=[[1., 0.]]))
    for text in ('<voice_0> talks', '<voice_1> listens', 'Rain falls'):
        g.add_text_node(dict(contents=[text], embeddings=[[1., 0.]]), 39)
    g.order_character()
    return g


def merge(snapshot):
    g = deepcopy(snapshot.graph)
    identity.apply_conclusions(g, {'p': {'canonical_name': 'Katrina'}}, [
        dict(observation_id='u0', feature_id='voice_0', entity_id='p'),
        dict(observation_id='u1', feature_id='voice_1', entity_id='p')], [],
        cutoff=snapshot.cutoff_timestamp, provenance={})
    return ConsolidationPatch(snapshot, g)


def wait(runtime):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        with runtime.lock:
            if runtime.job is None and runtime.index_job is None:
                return
        time.sleep(.005)
    raise AssertionError('runtime did not finish')


def test_diagnostic_close_does_not_consolidate_partial_window():
    g = graph()
    calls = []
    r = ConsolidationRuntime(g, lambda snapshot: calls.append(snapshot))
    with r.segment(39, 30):
        pass
    r.close(flush_final=False)
    assert not calls and r.closed
    assert g.last_consolidated_timestamp == 0


def test_streaming_hot_retrieval_snapshot_and_inheritance():
    g = graph()
    entered, release = threading.Event(), threading.Event()
    snapshots, batches = [], []
    def worker(s):
        snapshots.append(s); entered.set()
        assert release.wait(5)
        return merge(s)
    def embed(texts):
        batches.append(texts)
        return [[0., 1.] for _ in texts]
    r = ConsolidationRuntime(g, worker, embed=embed)
    try:
        with r.segment(39, 1200):
            pass
        assert entered.wait(2)
        for clip in range(40, 46):
            with r.segment(clip, 1200 + (clip - 39)*30):
                if clip == 40:
                    hot = g.add_voice_node(dict(contents=['new voice'], embeddings=[[1., 0.]]))
                    # Existing construction supplies a provisional character link.
                    g.character_mappings['character_1'].append('voice_' + str(hot))
                g.add_text_node(dict(contents=[f'<voice_{hot}> clip {clip}'], embeddings=[[1., 0.]]), clip)
        assert len(snapshots[0].graph.nodes) == 5
        assert all(clip in g.text_nodes_by_clip for clip in range(40, 46))
        assert len(r.read_graph().search_text_nodes([[1., 0.]])) == 9
        release.set(); wait(r)
        assert not r.errors
        assert g.resolve_identity('voice_' + str(hot))['identity'] == 'Katrina'
        assert g.nodes[hot].metadata['contents'] == ['new voice']
        assert len(batches) == 1 and len(batches[0]) == 8
        assert 'Rain falls' not in batches[0]
        assert g.nodes[4].embeddings == [[1., 0.]]
        assert g.last_consolidated_clip_id == 39
        assert g.last_completed_clip_id == 45
        restored = pickle.loads(pickle.dumps(g))
        assert not hasattr(restored, '_consolidation_runtime')
        assert restored.resolve_identity('voice_' + str(hot))['identity'] == 'Katrina'
    finally:
        release.set(); r.close()


def test_cutoff_protection_and_atomic_failure():
    g = graph()
    def invalid(snapshot):
        result = merge(snapshot)
        result.graph.add_text_node(dict(contents=['illegal'], embeddings=[[1., 0.]],
                                        retrieval_contents=['illegal']), 42)
        return result
    r = ConsolidationRuntime(g, invalid, embed=lambda texts: [])
    before = deepcopy(g.character_mappings)
    try:
        with r.segment(39, 1200): pass
        wait(r)
        assert r.errors and 'nodes or edges' in r.errors[0][1]
        assert g.character_mappings == before and g.identity_revision == 0
        assert g.last_consolidated_clip_id == -1
    finally:
        with pytest.raises(RuntimeError, match='requires retry'):
            r.close()
        r.worker = merge
        r.embed = lambda texts: [[0., 1.] for _ in texts]
        r.retry(); wait(r); r.close()


def test_worker_failure_retry_and_nonblocking_embedding():
    g = graph(); calls = []
    entered, release = threading.Event(), threading.Event()
    def worker(s):
        calls.append(s)
        if len(calls) == 1: raise RuntimeError('Astra failed')
        return merge(s)
    def embed(texts):
        entered.set(); assert release.wait(5)
        return [[0., 1.] for _ in texts]
    r = ConsolidationRuntime(g, worker, embed=embed)
    try:
        with r.segment(39, 1200): pass
        wait(r)
        assert g.identity_revision == 0
        r.retry(); assert entered.wait(2)
        assert g.identity_revision == 1
        assert g.nodes[2].metadata['embedding_stale']
        with r.segment(40, 1230):
            contents = identity.prepare_texts(g, ['<voice_0> hot'])
            g.add_text_node(dict(contents=['<voice_0> hot'], retrieval_contents=contents,
                                embeddings=[[1., 0.]]), 40)
        assert len(g.search_text_nodes([[1., 0.]])) == 4
        release.set(); wait(r)
        assert not g.identity_dirty and calls[0] is calls[1]
    finally: release.set(); r.close()


def test_appended_reviewed_cluster_loses_global_ownership():
    g = graph(); entered, release = threading.Event(), threading.Event()
    def worker(s):
        entered.set(); assert release.wait(5); return merge(s)
    r = ConsolidationRuntime(g, worker, embed=lambda texts: [[0., 1.] for _ in texts])
    try:
        with r.segment(39, 1200): pass
        assert entered.wait(2)
        with r.segment(40, 1230):
            g.update_node(0, dict(contents=['unreviewed'], embeddings=[[1., 0.]]))
        release.set(); wait(r)
        assert not r.errors
        assert g.resolve_identity('voice_0')['identity'] == 'voice_0'
        assert g.reviewed_feature_support['voice_0']['total'] == 2
        assert not g.reviewed_feature_support['voice_0']['complete']
        assert g.resolve_identity('voice_0', observation_id='u0')['identity'] == 'Katrina'
    finally: release.set(); r.close()


def test_index_failure_preserves_old_vectors_and_retries():
    g = graph(); batches = []
    def embed(texts):
        batches.append(texts)
        if len(batches) == 1: raise RuntimeError('embedding outage')
        return [[0., 1.] for _ in texts]
    r = ConsolidationRuntime(g, merge, embed=embed)
    try:
        with r.segment(39, 1200): pass
        wait(r)
        assert g.identity_revision == 1 and g.identity_dirty
        assert g.nodes[2].embeddings == [[1., 0.]]
        assert len(g.search_text_nodes([[1., 0.]])) == 3
        r.retry(); wait(r)
        assert not g.identity_dirty and len(batches) == 2
    finally: r.close()


def test_preserves_windows_backpressure_and_rebases_waiting_snapshot():
    g = graph(); entered, release = threading.Event(), threading.Event(); clips = []
    revisions = []
    def worker(s):
        clips.append(s.cutoff_clip_id)
        revisions.append(s.graph.identity_revision)
        if len(clips) == 1:
            entered.set(); assert release.wait(5)
        return merge(s)
    r = ConsolidationRuntime(g, worker, embed=lambda texts: [[0., 1.] for _ in texts])
    try:
        with r.segment(39, 1200): pass
        assert entered.wait(2)
        with r.segment(79, 2400): pass
        writing = threading.Event()
        def write_next():
            with r.segment(119, 3600):
                writing.set()
        writer = threading.Thread(target=write_next)
        writer.start()
        assert not writing.wait(.05)
        assert r.pending.cutoff_clip_id == 79
        assert clips == [39]
        release.set(); writer.join(5); assert not writer.is_alive()
        wait(r)
        assert clips == [39, 79, 119] and not r.errors
        assert revisions == [0, 1, 2]
        assert g.last_consolidated_clip_id == 119
    finally: release.set(); r.close()


def test_existing_native_application_adapter(tmp_path):
    from consolidation.runtime_io import NativeConsolidationWorker
    from consolidation.tests.test_native_characters import graph as fixture_graph, publication_inputs
    g = fixture_graph()
    replay, _, _, patch = publication_inputs(g)
    worker = NativeConsolidationWorker(lambda s: {'replay': replay},
                                      lambda packet, path: patch, tmp_path, moss=False)
    r = ConsolidationRuntime(g, worker, period_s=10, embed=lambda texts: [[0., 1., 0.] for _ in texts])
    try:
        with r.segment(1, 10): pass
        wait(r)
        assert not r.errors and g.identity_revision == 1
        assert (tmp_path/'snapshot_1/identity_changes.json').exists()
        assert g.resolve_identity('voice_1')['character_id'] == 'character_0'
    finally: r.close()


def test_commit_waits_for_clip_boundary_without_holding_writer_lock():
    g = graph(); entered, release = threading.Event(), threading.Event()
    def worker(s):
        entered.set(); assert release.wait(5); return merge(s)
    r = ConsolidationRuntime(g, worker, embed=lambda texts: [[0., 1.] for _ in texts])
    try:
        with r.segment(39, 1200): pass
        assert entered.wait(2)
        with r.segment(40, 1230):
            release.set()
            r.job.result(timeout=2)
            assert g.identity_revision == 0
            # Precomputed old-identity embeddings remain valid for the whole clip.
            g.add_text_node(dict(contents=['<voice_0> latest'], embeddings=[[1., 0.]]), 40)
        wait(r)
        assert g.identity_revision == 1 and not r.errors
        assert g.get_retrieval_contents(5) == ['Katrina latest']
    finally: release.set(); r.close()


def test_runtime_publisher_rolls_back_failed_mandol(tmp_path, monkeypatch):
    from consolidation.runtime_io import RetrievalPublisher
    from consolidation import reindex_cycle
    from consolidation.common import read, write
    g = graph()
    r = ConsolidationRuntime(g, merge, embed=lambda texts: [[0., 1.] for _ in texts])
    def build(staged, graph, config):
        write(staged/'mandol/index.json', {'version': graph.graph_version})
        return dict(status='ready', graph_version=graph.graph_version)
    monkeypatch.setattr(reindex_cycle, 'build_retrieval_bundle', build)
    publisher = RetrievalPublisher(tmp_path)
    try:
        with r.segment(39, 1200): pass
        wait(r)
        g.identity_session = 'runtime-test'
        publisher(deepcopy(g))
        previous = read(tmp_path/'CURRENT.json')
        def broken(*args): raise RuntimeError('Mandol unavailable')
        monkeypatch.setattr(reindex_cycle, 'build_retrieval_bundle', broken)
        g.current_graph_version += 1
        with pytest.raises(RuntimeError, match='Mandol unavailable'):
            publisher(deepcopy(g))
        assert read(tmp_path/'CURRENT.json') == previous
        assert VideoGraph.load_current(tmp_path).identity_revision == 1
        assert not list((tmp_path/'versions').glob('.staged-*'))
    finally: r.close()


def test_background_index_cannot_overwrite_a_newer_identity():
    g = graph(); entered, release = threading.Event(), threading.Event(); names = []
    def worker(s):
        result = merge(s)
        name = 'First' if not names else 'Corrected'
        names.append(name)
        for metadata in result.graph.character_metadata.values():
            metadata['canonical_name'] = name
        return result
    calls = []
    def embed(texts):
        calls.append(texts)
        if len(calls) == 1:
            entered.set(); assert release.wait(5)
        return [[0., 1.] for _ in texts]
    r = ConsolidationRuntime(g, worker, embed=embed)
    try:
        with r.segment(39, 1200): pass
        assert entered.wait(2)
        with r.segment(79, 2400): pass
        # Wait for the second reasoning result without waiting for the first index.
        deadline = time.monotonic() + 2
        while g.identity_revision < 2 and time.monotonic() < deadline:
            time.sleep(.005)
        assert g.identity_revision == 2
        release.set(); wait(r)
        assert not r.errors and not g.identity_dirty
        assert g.nodes[2].metadata['retrieval_contents'] == ['Corrected talks']
        assert len(calls) == 2
    finally: release.set(); r.close()


def test_snapshot_is_not_mutable_worker_storage():
    g = graph()
    def worker(s):
        result = merge(s)
        s.graph.nodes[2].metadata['contents'] = ['modified input']
        return result
    r = ConsolidationRuntime(g, worker)
    try:
        with r.segment(39, 1200): pass
        wait(r)
        assert 'modified its historical snapshot' in r.errors[0][1]
        assert g.nodes[2].metadata['contents'] == ['<voice_0> talks']
        assert g.identity_revision == 0
    finally:
        with pytest.raises(RuntimeError, match='requires retry'):
            r.close()
        r.worker = merge
        r.embed = lambda texts: [[0., 1.] for _ in texts]
        r.retry(); wait(r); r.close()


def test_hot_character_id_allocation_wins_collision():
    g = graph(); entered, release = threading.Event(), threading.Event()
    identity.initialize(g)
    g.character_metadata['character_0'] = {'canonical_name': 'Old', 'merged_character_ids': []}
    def worker(s):
        result = deepcopy(s.graph)
        identity.apply_conclusions(result, {'new': {'canonical_name': 'Corrected'}},
            [dict(observation_id='u0', feature_id='voice_0', entity_id='new')], [],
            cutoff=s.cutoff_timestamp, provenance={})
        entered.set(); assert release.wait(5)
        return ConsolidationPatch(s, result)
    r = ConsolidationRuntime(g, worker, embed=lambda texts: [[0., 1.] for _ in texts])
    try:
        with r.segment(39, 1200): pass
        assert entered.wait(2)
        with r.segment(40, 1230):
            hot = g.add_voice_node(dict(contents=['hot'], embeddings=[[1., 0.]]))
            g.refresh_equivalences()
            owner = g.resolve_identity('voice_' + str(hot))['character_id']
        release.set(); wait(r)
        assert not r.errors
        assert g.resolve_identity('voice_' + str(hot))['character_id'] == owner
        assert g.resolve_identity('voice_0')['identity'] == 'Corrected'
        assert g.resolve_identity('voice_0')['character_id'] != owner
    finally: release.set(); r.close()


def test_failed_window_blocks_waiting_window_until_retry_and_close_drains_tail():
    g = graph(); calls = []; first = threading.Event(); release = threading.Event()
    def worker(s):
        calls.append(s.cutoff_clip_id)
        if len(calls) == 1:
            first.set(); assert release.wait(5)
            raise RuntimeError('model offline')
        return merge(s)
    r = ConsolidationRuntime(g, worker, embed=lambda xs: [[0., 1.] for _ in xs])
    try:
        with r.segment(39, 1200): pass
        assert first.wait(2)
        with r.segment(79, 2400): pass
        with r.segment(80, 2430): pass
        release.set(); wait(r)
        assert calls == [39] and r.pending.cutoff_clip_id == 79
        with pytest.raises(RuntimeError, match='requires retry'):
            r.close()
        assert not r.closed and r.failed_snapshot.cutoff_clip_id == 39
        r.retry()
        r.close()
        assert calls == [39, 39, 79, 80]
        assert g.last_consolidated_timestamp == 2430
        r.close()
        assert calls == [39, 39, 79, 80]
    finally:
        release.set()
        if not r.closed:
            r.worker = merge
            wait(r)
            if r.failed_snapshot: r.retry()
            r.close()


def test_queued_identity_uses_live_collision_remap_without_future_evidence():
    g = graph(); entered = threading.Event(); release = threading.Event(); snapshots = []
    identity.initialize(g)
    g.character_metadata['character_0'] = {'canonical_name': 'Old', 'merged_character_ids': []}
    def worker(s):
        snapshots.append(s)
        result = deepcopy(s.graph)
        if len(snapshots) == 1:
            identity.apply_conclusions(result, {'new': {'canonical_name': 'Corrected'}},
                [dict(observation_id='u0', feature_id='voice_0', entity_id='new')], [],
                cutoff=s.cutoff_timestamp, provenance={})
            entered.set(); assert release.wait(5)
        else:
            result.identity_cutoff = s.cutoff_timestamp
            result.identity_revision += 1
        return ConsolidationPatch(s, result)
    r = ConsolidationRuntime(g, worker, embed=lambda xs: [[0., 1.] for _ in xs])
    try:
        with r.segment(39, 1200): pass
        assert entered.wait(2)
        with r.segment(79, 2400):
            queued_hot = g.add_voice_node(dict(contents=['queued'], embeddings=[[1., 0.]]))
            g.refresh_equivalences()
        with r.segment(80, 2430):
            later = g.add_voice_node(dict(contents=['future'], embeddings=[[1., 0.]]))
            g.refresh_equivalences()
        release.set(); wait(r)
        assert not r.errors and len(snapshots) == 2
        queued = snapshots[1].graph
        assert queued_hot in queued.nodes and later not in queued.nodes
        assert queued.identity_cutoff_clip == 39
        assert queued.resolve_identity('voice_0')['character_id'] == g.resolve_identity('voice_0')['character_id']
        assert queued.resolve_identity('voice_0')['identity'] == 'Corrected'
        assert queued.resolve_identity('voice_'+str(queued_hot))['character_id'] != queued.resolve_identity('voice_0')['character_id']
        assert queued.next_character_id > int(queued.resolve_identity('voice_0')['character_id'].split('_')[-1])
    finally:
        release.set(); r.close()
