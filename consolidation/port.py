"""Stable in-process and command-line boundary for native consolidation."""
import argparse
from copy import deepcopy
from dataclasses import dataclass
import fcntl
import json
import math
import time
from pathlib import Path

from .common import read, write


def attach_online(graph, evidence, directory, *, api_config=None, model=None,
                  proposer=None, moss=None, moss_config=None, period_s=1200, embed=None):
    """Attach a measured, caller-scheduled consolidation runtime.

    Construction uses runtime.segment(); after all peer graphs commit, call
    consolidate_until(cutoff). Scheduling, native commits, and reindexing belong
    to this package. The evidence callback only adapts the caller's source data.
    """
    from .runtime import ConsolidationRuntime
    from .llm_consolidator import propose_official
    from .moss_local import LocalWindowMoss
    directory=Path(directory)
    if proposer is None:
        if not api_config or not model:
            raise ValueError('supply a proposer or explicit model and API configuration')
        def proposer(packet, work):
            return propose_official(packet,work,api_config,model=model)
    if moss is None and moss_config is not None:
        moss=LocalWindowMoss(moss_config['checkpoint'],moss_config['revision'],moss_config['repository'])
    timings={}
    def measured_evidence(snapshot):
        started=time.perf_counter();value=evidence(snapshot)
        timings['snapshot_input_preparation_ms']=(time.perf_counter()-started)*1000
        return value
    def measured_proposer(packet, work):
        started=time.perf_counter();value=proposer(packet,work)
        timings['llm_ms']=(time.perf_counter()-started)*1000
        if model:
            meta=read(work/'llm_metadata.json')
            if meta['returned_model']!=model:
                raise ValueError('consolidation model mismatch')
            timings['usage']=meta.get('usage')
        return value
    worker=make_worker(measured_evidence,measured_proposer,directory,moss=moss)

    class BoundaryRuntime(ConsolidationRuntime):
        hold=True
        pending_perf=None

        def _schedule(self):
            if self.pending is not None and self.pending_perf is None:
                self.pending_perf=time.perf_counter()
            if not self.hold:
                super()._schedule()

        def _snapshot(self):
            started=time.perf_counter();value=super()._snapshot()
            self.snapshot_copy_ms=(time.perf_counter()-started)*1000
            return value

        def _launch(self,snapshot):
            self.queued_perf=time.perf_counter()
            super()._launch(snapshot)

        def _reason(self,snapshot):
            self.event_perf=time.perf_counter();timings.clear()
            timings.update(cutoff=snapshot.cutoff_timestamp,input_nodes=len(snapshot.graph.nodes),
                consolidation_start=time.time(),snapshot_copy_ms=self.snapshot_copy_ms,
                queue_ms=(self.event_perf-(self.pending_perf or self.queued_perf))*1000,
                before_mappings=deepcopy(snapshot.graph.character_mappings))
            result=super()._reason(snapshot)
            timings['reason_worker_ms']=(time.perf_counter()-self.event_perf)*1000
            job=directory/('snapshot_'+str(snapshot.graph_version))
            timings['phase_timings']=read(job/'phase_timings.json')
            execution=read(job/'execution.json')
            timings.update(accepted_decisions=len(execution.get('accepted',[])),
                rejected_decisions=len(execution.get('rejected',[])),job_directory=str(job))
            self.pending_perf=None
            return result

        def _commit(self,patch):
            started=time.perf_counter();super()._commit(patch)
            timings['write_back_ms']=(time.perf_counter()-started)*1000
            timings['after_mappings']=deepcopy(self.graph.character_mappings)
            timings['affected_nodes']=[n.id for n in self.graph.nodes.values() if n.metadata.get('embedding_stale')]

        def _build_index(self,g):
            started=time.perf_counter();result=super()._build_index(g)
            timings['reindex_ms']=(time.perf_counter()-started)*1000
            timings['reindex_report']=result
            return result

        def consolidate_until(self,cutoff,progress=None):
            started=time.perf_counter()
            with self.condition:
                if self.errors:raise RuntimeError('scheduled consolidation failed: '+repr(self.errors))
                if self.active or cutoff!=self.last_time:
                    raise ValueError('consolidation requires the exact committed writer boundary')
                if self.graph.last_consolidated_timestamp==cutoff:
                    raise ValueError('boundary already consolidated')
                if self.pending is None and self.job is None:
                    self.pending=self._snapshot()
                self.hold=False
                self._schedule()
                self.hold=True
                while self.job is not None or self.index_job is not None:
                    self.condition.wait(timeout=30)
                    if progress:progress(cutoff,time.perf_counter()-started)
                if self.errors:raise RuntimeError('scheduled consolidation failed: '+repr(self.errors))
                if self.graph.last_consolidated_timestamp!=cutoff or self.graph.identity_dirty:
                    raise RuntimeError('consolidation or native reindex incomplete')
                return dict(timings,consolidation_end=time.time(),
                    total_consolidation_wall_ms=(time.perf_counter()-self.event_perf)*1000,
                    construction_blocked_ms=(time.perf_counter()-started)*1000,
                    llm_call_count=1,status='accepted',media_timestamp=cutoff)

        def close(self,*,flush_final=True):
            self.hold=False
            return super().close(flush_final=flush_final)

    return BoundaryRuntime(graph,worker,period_s=period_s,embed=embed)


def make_worker(evidence, proposer, directory, *, moss=None):
    """Streaming port: return the existing snapshot worker with measured I/O.

    Evidence may provide ``assignment_jsonl`` for a concurrently appended log.
    Attach the returned callable to ConsolidationRuntime for native commit/reindex.
    """
    from .runtime_io import NativeConsolidationWorker
    def inputs(snapshot):
        value = dict(evidence(snapshot))
        if 'assignment_jsonl' in value:
            value['assignments'] = fetch_voice_log(value.pop('assignment_jsonl'), value['replay'])
        return value
    worker = NativeConsolidationWorker(inputs, proposer, directory, moss=moss)
    def run(snapshot):
        started = time.perf_counter()
        result = worker(snapshot)
        job = Path(directory) / ('snapshot_' + str(snapshot.graph_version))
        execution = read(job / 'execution.json')
        if execution.get('rejected') and not execution.get('accepted'):
            raise ValueError('all proposed consolidation decisions were rejected')
        write(job / 'phase_timings.json', {'worker_wall_ms': (time.perf_counter()-started)*1000,
            'scope': 'shared worker including evidence, MOSS, reasoning and projection'})
        return result
    return run


def fetch_voice_log(path, replay):
    """Read a consistent prefix of AssignmentLogger's append-only JSONL.

    Retain historical anchors, but exclude uncommitted observations and future
    events. Never recompute scores from the current embedding pool.
    """
    observations = {o['utterance_id'] for o in replay['observations']}
    selected = {}
    with Path(path).open() as handle:
        fcntl.flock(handle, fcntl.LOCK_SH)
        for line in handle:
            if not line.strip():
                continue
            event = json.loads(line)
            if event['session_id'] != replay['session_id']:
                raise ValueError('voice log session mismatch')
            if not math.isfinite(event['available_at']):
                raise ValueError('invalid voice log timestamp')
            if event['available_at'] > replay['current_cutoff'] or event['utterance_id'] not in observations:
                continue
            key = event['evidence_id']
            if key in selected and selected[key] != event:
                raise ValueError('conflicting immutable voice evidence: ' + key)
            selected[key] = event
    return list(selected.values())


@dataclass(frozen=True)
class ConsolidationResult:
    graph: object
    directory: Path
    report: dict
    voice_log: Path


def consolidate(graph, replay, *, assignment_jsonl, work, output, proposer,
                moss=None, moss_runner=None, allow_no_moss=False, embedder=None):
    """Consolidate a committed VideoGraph and return its published successor.

    Call at a writer barrier. Input graph is never mutated. ``replay`` is the
    existing full-prefix evidence contract; a graph alone lacks original audio
    references and assignment scores. ``proposer(packet, work)`` selects the
    existing model transport. Publication includes native and Mandol reindexing.
    """
    from .pipeline import prepare, publish
    from .native import load_graph

    if getattr(graph, '_consolidation_runtime', None) is not None:
        raise ValueError('use the attached runtime for a live graph, or pass its frozen snapshot')
    if moss is None and moss_runner is None and not allow_no_moss:
        raise ValueError('supply exact-window MOSS evidence or a MOSS runner')
    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)
    inputs = deepcopy(replay)
    frozen = deepcopy(graph)
    assignments = fetch_voice_log(assignment_jsonl, inputs)
    voice_log = work / 'voice_similarity.json'
    write(voice_log, assignments)
    if moss is None and moss_runner is not None:
        moss = moss_runner(inputs, getattr(frozen, 'identity_cutoff', 0), work / 'moss')
    state, packet = prepare(inputs, output, moss, assignments, native_graph=frozen)
    write(work / 'evidence.json', packet)
    from .prompt_packet import prepare_prompt
    prepare_prompt(packet, work)
    patch = proposer(packet, work)
    destination, report = publish(inputs, output, state, packet, patch,
                                  embedder=embedder, llm_artifacts=work)
    result = ConsolidationResult(load_graph(destination / 'graph.pkl'), destination, report, voice_log)
    write(work / 'result.json', dict(graph=str(destination / 'graph.pkl'),
        directory=str(destination), voice_log=str(voice_log), report=report))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('native-graph', 'replay-json', 'assignment-jsonl', 'work', 'output'):
        parser.add_argument('--' + name, required=True)
    transport = parser.add_mutually_exclusive_group(required=True)
    transport.add_argument('--patch')
    transport.add_argument('--official-config')
    transport.add_argument('--endpoint')
    parser.add_argument('--model', default='gpt-6-astra')
    parser.add_argument('--moss-json')
    parser.add_argument('--moss-endpoint')
    parser.add_argument('--media-root')
    parser.add_argument('--moss-revision', default='server-unspecified')
    args = parser.parse_args()
    from .native import load_graph
    from .llm_consolidator import propose, propose_official
    from .moss_runner import WindowMoss
    if bool(args.moss_endpoint) != bool(args.media_root):
        parser.error('--moss-endpoint and --media-root must be supplied together')
    if not args.patch and not (args.moss_json or args.moss_endpoint):
        parser.error('live consolidation requires MOSS evidence or a window runner')
    def proposer(packet, work):
        if args.official_config:
            return propose_official(packet, work, args.official_config, args.model)
        return propose(packet, work, args.model, args.endpoint, patch_file=args.patch)
    result = consolidate(load_graph(args.native_graph), read(args.replay_json),
        assignment_jsonl=args.assignment_jsonl, work=args.work, output=args.output,
        proposer=proposer, moss=read(args.moss_json) if args.moss_json else None,
        moss_runner=WindowMoss(args.moss_endpoint, args.media_root, revision=args.moss_revision)
            if args.moss_endpoint else None, allow_no_moss=bool(args.patch))
    print(json.dumps(dict(graph=str(result.directory / 'graph.pkl'), report=result.report)))


if __name__ == '__main__':
    main()
