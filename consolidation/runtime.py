"""Single-writer streaming coordination with bounded, ordered evidence windows.

Model calls and embedding calls run on workers. The existing clip writer owns
nodes/edges; a worker can commit identity/index results only between clips.
"""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from copy import copy, deepcopy
from dataclasses import dataclass
import threading
import pickle

from .native import m3_module

IDENTITY_FIELDS = (
    'character_mappings', 'character_metadata', 'observation_character_mappings',
    'reference_character_mappings', 'identity_observations', 'reviewed_feature_support',
    'retired_character_ids', 'next_character_id', 'identity_revision', 'identity_history',
    'identity_cutoff', 'identity_cutoff_clip', 'identity_session',
    'memory_claim_revisions', 'character_constraints',
)


@dataclass(frozen=True)
class ConsolidationSnapshot:
    graph_version: int
    cutoff_clip_id: int
    cutoff_timestamp: float
    graph: object


@dataclass(frozen=True)
class ConsolidationPatch:
    snapshot: ConsolidationSnapshot
    graph: object  # Only native identity fields may differ from the snapshot.


def validate_patch(patch):
    """Expensive source integrity checks run on the worker, before commit."""
    base, result = patch.snapshot.graph, patch.graph
    if set(base.nodes) != set(result.nodes) or base.edges != result.edges:
        raise ValueError('runtime patch may not edit nodes or edges')
    for key, node in base.nodes.items():
        other = result.nodes[key]
        if (node.type != other.type or node.metadata != other.metadata
                or pickle.dumps(node.embeddings) != pickle.dumps(other.embeddings)):
            raise ValueError('runtime patch may only change native identity state')
    for record in getattr(result, 'reference_character_mappings', {}).values():
        node = base.nodes.get(int(record['node_id']))
        if node is None or node.metadata.get('timestamp', 0) > patch.snapshot.cutoff_clip_id:
            raise ValueError('reference outside historical cutoff')
    if getattr(result, 'identity_cutoff', 0) > patch.snapshot.cutoff_timestamp:
        raise ValueError('identity evidence exceeds snapshot cutoff')
    if getattr(result, 'identity_cutoff_clip', 0) > patch.snapshot.cutoff_clip_id:
        raise ValueError('identity clip exceeds snapshot cutoff')


def reconcile(live, patch, *, committed_remap=None, remap_out=None):
    """Three-way native identity merge; never replace live nodes or edges."""
    identity = m3_module('mmagent.character_identity')
    base, result = patch.snapshot.graph, patch.graph
    for key, node in base.nodes.items():
        current = live.nodes.get(key)
        if current is None or current.type != node.type:
            raise ValueError('historical node removed or replaced')
        old, now = node.metadata.get('contents', []), current.metadata.get('contents', [])
        if (now[:len(old)] != old or
                (node.type in ('semantic', 'episodic') and now != old)):
            raise ValueError('historical source changed since snapshot')
    if live.identity_revision != base.identity_revision:
        raise ValueError('identity base changed since snapshot')
    if getattr(result, 'identity_cutoff', 0) > patch.snapshot.cutoff_timestamp:
        raise ValueError('identity evidence exceeds snapshot cutoff')
    staged = copy(live)
    for field in IDENTITY_FIELDS:
        if hasattr(live, field):
            setattr(staged, field, deepcopy(getattr(live, field)))
    # New IDs allocated by hot construction take priority over worker-local IDs.
    remap = dict(committed_remap or {})
    used = set(live.character_mappings) | set(live.retired_character_ids)
    next_id = max(live.next_character_id, result.next_character_id)
    if committed_remap is None:
        for char in sorted(set(result.character_mappings) - set(base.character_mappings)):
            if char in used:
                remap[char] = 'character_' + str(next_id)
                next_id += 1
    if remap:
        next_id = max(next_id, max(int(c.split('_')[-1]) + 1 for c in remap.values()))
    if remap_out is not None:
        remap_out.update(remap)
    def mapped(value):
        if isinstance(value, str):
            return remap.get(value, value)
        if isinstance(value, list):
            return [mapped(v) for v in value]
        if isinstance(value, dict):
            return {remap.get(k, k): mapped(v) for k, v in value.items()}
        return deepcopy(value)
    after = {f: mapped(getattr(result, f)) for f in IDENTITY_FIELDS if hasattr(result, f)}
    retired = {}
    for char, metadata in after['character_metadata'].items():
        for old in metadata.get('merged_character_ids', []):
            if old in base.character_mappings and old not in after['character_mappings']:
                retired[old] = char
    base_features = {f for fs in base.character_mappings.values() for f in fs}
    reviewed = set(after['reviewed_feature_support'])
    historical_features = base_features | reviewed
    # Replace only historical feature ownership. Hot features keep their owner,
    # redirected through an accepted native merge (no person identity namespace).
    owners = {f: retired.get(c, c) for c, fs in live.character_mappings.items()
              for f in fs if f not in historical_features}
    owners.update({f: c for c, fs in after['character_mappings'].items() for f in fs})
    chars = (set(live.character_mappings) | set(after['character_mappings'])) - set(retired)
    staged.character_mappings = {c: [] for c in chars}
    for feature, owner in owners.items():
        staged.character_mappings[owner].append(feature)
    for field in ('character_metadata', 'observation_character_mappings',
                  'reference_character_mappings', 'identity_observations',
                  'reviewed_feature_support', 'memory_claim_revisions'):
        before = getattr(base, field, {})
        target = getattr(staged, field, {})
        updated = after.get(field, {})
        for key in set(before) - set(updated):
            target.pop(key, None)
        for key, value in updated.items():
            if key not in before or value != before[key]:
                target[key] = deepcopy(value)
        setattr(staged, field, target)
    for old in retired:
        staged.character_metadata.pop(old, None)
    staged.observation_character_mappings = {
        k: retired.get(v, v) for k, v in staged.observation_character_mappings.items()}
    for field in ('reference_character_mappings', 'identity_observations'):
        for record in getattr(staged, field).values():
            if record.get('character_id') in retired:
                record['character_id'] = retired[record['character_id']]
    # Appends to reviewed raw clusters invalidate completeness. Admit only new
    # observations using the existing strict >75% rule and retain minority votes.
    staged.identity_revision = after['identity_revision']
    for feature in reviewed:
        node_id = int(feature.split('_')[-1])
        if node_id not in base.nodes:
            raise ValueError('reviewed feature is outside the snapshot')
        old_count = len(base.nodes[node_id].metadata.get('contents', []))
        new_contents = live.nodes[node_id].metadata.get('contents', [])[old_count:]
        if new_contents:
            # Re-admit suffix placeholders against the newly reviewed prefix.
            for index in range(old_count, old_count + len(new_contents)):
                uid = f'{feature}/content_{index}'
                if not staged.identity_observations.get(uid, {}).get('reviewed'):
                    staged.identity_observations.pop(uid, None)
                    staged.observation_character_mappings.pop(uid, None)
            identity.admit_observations(staged, feature, new_contents, old_count)
    for field in ('identity_revision', 'identity_history', 'identity_cutoff',
                  'identity_cutoff_clip', 'identity_session', 'character_constraints'):
        if field in after:
            setattr(staged, field, after[field])
    staged.retired_character_ids = sorted(set(live.retired_character_ids) | set(after['retired_character_ids']))
    staged.next_character_id = next_id
    identity.rebuild_reverse(staged)
    for char in staged.observation_character_mappings.values():
        if char not in staged.character_mappings:
            raise ValueError('invalid scoped character target')
    return staged


class ConsolidationRuntime:
    """Attach once to the existing ordered M3 clip writer; opt-in only.

    worker(snapshot) returns a ConsolidationPatch using existing reasoning logic.
    publish_index(graph) optionally builds/publishes a Mandol bundle off-thread.
    """
    def __init__(self, graph, worker, *, period_s=1200, embed=None, publish_index=None):
        if period_s <= 0 or getattr(graph, '_consolidation_runtime', None):
            raise ValueError('invalid period or runtime already attached')
        self.identity = m3_module('mmagent.character_identity')
        self.identity.initialize(graph)
        self.graph, self.worker = graph, worker
        self.period_s, self.embed, self.publish_index = period_s, embed, publish_index
        self.lock = threading.RLock()
        self.condition = threading.Condition(self.lock)
        self.pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix='m3-consolidation')
        self.active = self.closed = False
        self.closing = False
        self.job = self.index_job = None
        self.pending = None
        self.writer_waiting = False
        self.failed_snapshot = None
        self.errors = []
        self.index_failed = False
        self.publication_pending = False
        self.ready = []
        self.last_clip = getattr(graph, 'last_completed_clip_id', -1)
        self.last_time = getattr(graph, 'last_completed_timestamp', 0.)
        graph.current_graph_version = getattr(graph, 'current_graph_version', 0)
        graph.last_consolidated_clip_id = getattr(graph, 'last_consolidated_clip_id', -1)
        graph.last_consolidated_timestamp = getattr(graph, 'last_consolidated_timestamp', 0.)
        graph.entity_registry_version = graph.identity_revision
        graph.identity_reindex_async = True
        graph.identity_runtime_active = True
        graph._consolidation_runtime = self
        self.boundary = (int(graph.last_consolidated_timestamp // period_s) + 1) * period_s

    @contextmanager
    def segment(self, clip_id, cutoff_timestamp):
        """One existing construction call. No lock is held during that call."""
        with self.lock:
            if (self.closed or self.closing or self.active or self.writer_waiting
                    or clip_id <= self.last_clip or cutoff_timestamp < self.last_time):
                raise ValueError('runtime requires one ordered clip writer')
            self._drain()
            self.writer_waiting = True
            try:
                while cutoff_timestamp >= self.boundary and self.pending is not None:
                    self.condition.wait()
                    if self.closed or self.closing:
                        raise ValueError('runtime is closing')
                    self._drain()
            finally:
                self.writer_waiting = False
            self.active = True
        try:
            yield
        except BaseException:
            with self.lock:
                self.active = False
            raise
        else:
            with self.lock:
                self.active = False
                self.last_clip, self.last_time = clip_id, cutoff_timestamp
                self.graph.last_completed_clip_id = clip_id
                self.graph.last_completed_timestamp = cutoff_timestamp
                self.graph.current_graph_version += 1
                self.index_failed = False
                self._drain()
                if cutoff_timestamp >= self.boundary:
                    self.pending = self._snapshot()
                    self.boundary = (int(cutoff_timestamp // self.period_s) + 1) * self.period_s
                self._schedule()
                self._index()
                self.condition.notify_all()

    def _snapshot(self):
        return ConsolidationSnapshot(self.graph.current_graph_version, self.last_clip,
                                     self.last_time, deepcopy(self.graph))

    def read_graph(self):
        """A request-local read snapshot, including completed hot memories."""
        with self.lock:
            return deepcopy(self.graph)

    def _schedule(self):
        if (self.closed or self.active or self.job is not None or self.failed_snapshot is not None
                or self.pending is None):
            return
        snapshot = self.pending
        self.pending = None
        self._launch(snapshot)
        self.condition.notify_all()

    def _launch(self, snapshot):
        self.job = self.pool.submit(self._reason, snapshot)
        self.job.add_done_callback(lambda f: self._complete('patch', snapshot, f))

    def _reason(self, snapshot):
        frozen = pickle.dumps(snapshot.graph)
        try:
            result = self.worker(snapshot)
            if not isinstance(result, ConsolidationPatch) or result.snapshot is not snapshot:
                raise ValueError('patch belongs to another historical snapshot')
            if pickle.dumps(snapshot.graph) != frozen:
                raise ValueError('worker modified its historical snapshot')
            validate_patch(result)
            return result
        except BaseException:
            # A faulty worker must not poison the frozen window retained for retry.
            original = pickle.loads(frozen)
            snapshot.graph.__dict__.clear()
            snapshot.graph.__dict__.update(original.__dict__)
            raise

    def _complete(self, kind, snapshot, future):
        with self.lock:
            self.ready.append((kind, snapshot, future))
            if not self.active:
                self._drain()
                self._schedule()
                self._index()
            self.condition.notify_all()

    def _drain(self):
        while self.ready:
            kind, snapshot, future = self.ready.pop(0)
            try:
                result = future.result()
                if kind == 'patch':
                    if not isinstance(result, ConsolidationPatch) or result.snapshot is not snapshot:
                        raise ValueError('patch belongs to another historical snapshot')
                    self._commit(result)
                    self.failed_snapshot = None
                else:
                    self._install_index(snapshot, result)
            except Exception as error:
                self.errors.append((kind, str(error)))
                if kind == 'patch':
                    self.failed_snapshot = snapshot
                else:
                    self.index_failed = True
            finally:
                if kind == 'patch':
                    self.job = None
                else:
                    self.index_job = None

    def _commit(self, patch):
        remap = {}
        staged = reconcile(self.graph, patch, remap_out=remap)
        staged.identity_cutoff_clip = patch.snapshot.cutoff_clip_id
        pending = self.pending
        if pending is not None:
            # Rebase only identity fields, with IDs chosen by the live commit.
            # The queued graph's raw prefix and embeddings stay frozen.
            rebased = reconcile(pending.graph, patch, committed_remap=remap)
            rebased.next_character_id = max(rebased.next_character_id, staged.next_character_id)
            rebased.identity_cutoff_clip = patch.snapshot.cutoff_clip_id
            rebased.last_consolidated_clip_id = patch.snapshot.cutoff_clip_id
            rebased.last_consolidated_timestamp = patch.snapshot.cutoff_timestamp
            rebased.entity_registry_version = rebased.identity_revision
            pending = ConsolidationSnapshot(pending.graph_version, pending.cutoff_clip_id,
                                            pending.cutoff_timestamp, rebased)
        # Validate all canonical texts before touching the live state.
        changed = []
        for node in self.graph.nodes.values():
            if node.type in ('semantic', 'episodic'):
                text, _ = self.identity.canonicalize_contents(staged, node.metadata['contents'], node_id=node.id)
                if text != node.metadata.get('retrieval_contents', node.metadata['contents']):
                    changed.append(node.id)
        fields = {f: getattr(staged, f) for f in IDENTITY_FIELDS if hasattr(staged, f)}
        fields.update(reverse_character_mappings=staged.reverse_character_mappings,
            entity_registry_version=staged.identity_revision, identity_dirty=bool(changed),
            current_graph_version=self.graph.current_graph_version + 1,
            last_consolidated_clip_id=patch.snapshot.cutoff_clip_id,
            last_consolidated_timestamp=patch.snapshot.cutoff_timestamp)
        self.graph.__dict__.update(fields)
        self.pending = pending
        self.publication_pending = self.publish_index is not None
        changed = set(changed)
        for node in self.graph.nodes.values():
            if node.id in changed:
                node.metadata['embedding_stale'] = True
            elif node.type in ('semantic', 'episodic'):
                node.metadata.pop('embedding_stale', None)

    def _index(self):
        if (self.closed or self.active or self.index_failed or self.index_job is not None
                or not (self.graph.identity_dirty or self.publication_pending)):
            return
        snapshot = deepcopy(self.graph)
        self.index_job = self.pool.submit(self._build_index, snapshot)
        self.index_job.add_done_callback(lambda f: self._complete('index', snapshot, f))

    def _build_index(self, graph):
        report = self.identity.reindex_text(graph, self.embed)
        if self.publish_index:
            self.publish_index(graph)
        return report

    def _install_index(self, snapshot, report):
        if snapshot.identity_revision != self.graph.identity_revision:
            return  # A newer identity revision wins; schedule a fresh background pass.
        self.publication_pending = False
        changed = set(report['changed_node_ids'])
        for node_id in report['changed_node_ids'] + report['unchanged_text_node_ids']:
            source, target = snapshot.nodes[node_id], self.graph.nodes.get(node_id)
            if target is None or target.metadata['contents'] != source.metadata['contents']:
                continue
            current, _ = self.identity.canonicalize_contents(self.graph, target.metadata['contents'], node_id=node_id)
            if current != source.metadata['retrieval_contents']:
                continue
            if node_id in changed:
                target.embeddings = source.embeddings
            for key in ('retrieval_contents', 'retrieval_identity_trace', 'embedding_input_fingerprint'):
                target.metadata[key] = source.metadata[key]
            target.metadata.pop('embedding_stale', None)
        self.graph.identity_dirty = any(
            self.identity.canonicalize_contents(self.graph, n.metadata['contents'], node_id=n.id)[0]
            != n.metadata.get('retrieval_contents', n.metadata['contents'])
            for n in self.graph.nodes.values() if n.type in ('semantic', 'episodic'))

    def retry(self):
        with self.lock:
            if self.active or self.job is not None or self.closed:
                raise ValueError('retry requires an idle writer and worker')
            if self.failed_snapshot:
                self._launch(self.failed_snapshot)
            self.index_failed = False
            self._index()

    def close(self, *, flush_final=True):
        """Drain ordered windows and one final tail; a failed window remains retryable."""
        with self.lock:
            if self.closed:
                return
            if self.active:
                raise ValueError('finish the current clip before closing')
            self.closing = True
            self.condition.notify_all()
            while True:
                self._drain()
                self._schedule()
                self._index()
                if self.job is not None or self.index_job is not None:
                    self.condition.wait()
                    continue
                if self.failed_snapshot is not None or self.index_failed:
                    self.closing = False
                    raise RuntimeError('consolidation shutdown requires retry: ' + str(self.errors[-1:]))
                if flush_final and self.last_time > self.graph.last_consolidated_timestamp:
                    self.pending = self._snapshot()
                    continue
                break
            self.closed = True
        self.pool.shutdown(wait=True)
        with self.lock:
            self._drain()
        self.graph._consolidation_runtime = None
