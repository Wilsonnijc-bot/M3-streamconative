"""Bounded model-facing evidence; the full packet remains executor authority."""
from collections import Counter, defaultdict
import json
import os
import re

from .common import write

FORMAT_VERSION = 2
HISTORY_BYTES = 64 * 1024
PACKET_BYTES = 512 * 1024


def compact(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False,
                      separators=(',', ':'))


def byte_size(value):
    return len(compact(value).encode('utf-8'))


class PromptBudgetError(ValueError):
    def __init__(self, report):
        self.report = report
        super().__init__('prompt packet exceeds byte budget: ' + compact(report))


def _observation(o):
    alternatives = defaultdict(list)
    for source, text in o.get('transcripts', {}).items():
        alternatives[text].append(source)
    if not alternatives and o.get('original_transcript'):
        alternatives[o['original_transcript']].append('unknown')
    result = {k: o[k] for k in ('utterance_id', 'clip_id', 'start_time', 'end_time',
                               'original_voice_id', 'current_entity_id') if k in o}
    result['transcripts'] = [dict(text=t, sources=sorted(s))
                             for t, s in sorted(alternatives.items())]
    provenance = o.get('original_assignment_evidence', {})
    result['quality'] = {k: provenance[k] for k in
                         ('assignment_status', 'scores_status', 'candidate_voice_ids')
                         if k in provenance}
    return result


def _memory(m):
    result = {k: m[k] for k in ('evidence_id', 'memory_node_id', 'kind', 'clip_id',
                               'available_at')}
    result['contents'] = m.get('raw_contents', [m['raw_text']])
    return result


def build_prompt_packet(packet, *, history_bytes=HISTORY_BYTES, packet_bytes=PACKET_BYTES):
    """Return (model view, executor scope, size report), without changing evidence."""
    if history_bytes < 0 or packet_bytes <= 0:
        raise ValueError('invalid prompt byte budgets')
    previous, cutoff = packet['previous_cutoff'], packet['current_cutoff']
    observations = {o['utterance_id']: o for o in packet['observations']}
    memories = {m['evidence_id']: m for m in packet['memories']}
    all_records = list(observations.values()) + list(memories.values())
    previous_clip = packet.get('previous_cutoff_clip')
    if previous_clip is None:
        previous_clip = max([r['clip_id'] for r in all_records
                             if r.get('available_at', r.get('end_time')) <= previous] or [-1])
    current_clip = packet.get('current_cutoff_clip', max([r['clip_id'] for r in all_records] or [-1]))
    for r in all_records:
        end = r.get('available_at', r.get('end_time'))
        if end > cutoff or r['clip_id'] > current_clip:
            raise ValueError('evidence exceeds committed boundary')
        if (r['clip_id'] <= previous_clip) != (end <= previous):
            raise ValueError('clip boundary disagrees with previous time cutoff')
    new_obs = {u for u, o in observations.items() if o['clip_id'] > previous_clip}
    new_mem = {e for e, m in memories.items() if m['clip_id'] > previous_clip}
    old_obs, old_mem = set(observations) - new_obs, set(memories) - new_mem
    views = {u: _observation(o) for u, o in observations.items()}
    views.update({e: _memory(m) for e, m in memories.items()})
    alignments = {a['utterance_id']: a for a in packet.get('moss_alignments', [])}
    moss = packet.get('moss') or {}
    if moss:
        from .moss_alignment import validate_window
        validate_window(moss,packet['session_id'],previous,cutoff)
    segments = moss.get('segments', [])
    run = moss.get('run_id')
    segment_views = {str(i): {k: s[k] for k in ('start', 'end', 'speaker', 'text')}
                     for i, s in enumerate(segments)}
    overlapping = {u: [str(i) for i, s in enumerate(segments)
                      if s['start'] < o['end_time'] and s['end'] > o['start_time']]
                   for u, o in observations.items()}
    assignment_views = []
    for a in packet.get('original_assignments', []):
        row = {k: a[k] for k in ('evidence_id', 'utterance_id', 'method', 'threshold',
               'selected_candidate', 'decision', 'reason') if k in a}
        row['candidates'] = [{k: c[k] for k in ('candidate_id', 'score', 'eligible',
                             'rejection_reason') if k in c} for c in a.get('candidates', [])]
        assignment_views.append(row)
    references = packet.get('current_references', {})

    def attachments(ids, include_window=False):
        selected_obs = ids & set(observations)
        selected_segments = {i for u in selected_obs for i in overlapping[u]}
        if include_window:
            selected_segments.update(str(i) for i, s in enumerate(segments)
                                     if s['end'] > previous and s['start'] < cutoff)
        alignment_views = []
        for u in sorted(selected_obs & set(alignments)):
            a = alignments[u]
            alignment_views.append(dict(evidence_id=a['evidence_id'], utterance_id=u,
                alignment_status=a['alignment_status'], segment_ids=overlapping[u]))
        mids = {str(memories[e]['memory_node_id']) for e in ids & set(memories)}
        return dict(records=[views[i] for i in sorted(ids)],
                    alignments=alignment_views,
                    moss_segments={i: segment_views[i] for i in sorted(selected_segments, key=int)},
                    assignment_evidence=[a for a in assignment_views if a.get('utterance_id') in selected_obs],
                    references=[{k: r[k] for k in ('memory_node_id', 'mention', 'entity_id',
                                'content_index', 'start', 'end') if k in r}
                                for r in references.values() if str(r['memory_node_id']) in mids],
                    claim_status={str(mid): r['status'] for mid, r in packet.get('current_claims', {}).items()
                                  if str(mid) in mids})

    new_voices = {observations[u].get('original_voice_id') for u in new_obs} - {None}
    new_speakers = {alignments[u].get('speaker') for u in new_obs & set(alignments)} - {None}
    registry = packet['registry']
    names_in_window = '\n'.join(m['raw_text'] for e, m in memories.items() if e in new_mem)
    name_support = {eid for entity in registry.values() for eid in entity.get('name_evidence', [])}

    def linked(u):
        return (observations[u].get('original_voice_id') in new_voices or
                alignments.get(u, {}).get('speaker') in new_speakers)

    def rank(eid):
        record = observations.get(eid, memories.get(eid))
        same_voice = (record.get('original_voice_id') in new_voices if eid in observations else
                      any('<' + v + '>' in record['raw_text'] for v in new_voices))
        same_speaker = eid in observations and alignments.get(eid, {}).get('speaker') in new_speakers
        return (eid not in name_support, not same_voice, not same_speaker,
                -record.get('available_at', record.get('end_time')), eid)

    # Round-robin selection gives each character an opportunity before extra anchors.
    candidates = {}
    for char, entity in sorted(registry.items()):
        obs = sorted((u for u in old_obs if observations[u].get('current_entity_id') == char), key=rank)[:2]
        mids = {str(r['memory_node_id']) for r in references.values() if r['entity_id'] == char}
        feature_ids = set(entity.get('voice_ids', []))
        mem = sorted((e for e in old_mem if e in entity.get('name_evidence', []) or
                      str(memories[e]['memory_node_id']) in mids or
                      any('<' + v + '>' in memories[e]['raw_text'] for v in feature_ids)), key=rank)[:2]
        candidates[char] = sorted(obs + mem, key=rank)
    selected = set()

    def admit(eid):
        proposed = selected | {eid}
        if byte_size(attachments(proposed)) <= history_bytes:
            selected.add(eid)

    ordered_chars = sorted(registry, key=lambda c: (
        not (registry[c].get('canonical_name') and registry[c]['canonical_name'] in names_in_window), c))
    for index in range(4):
        for char in ordered_chars:
            if index < len(candidates[char]):
                admit(candidates[char][index])
    # Only linked unresolved turns or turns in mixed/conflicting voices are candidates.
    voice_entities = defaultdict(set)
    for o in observations.values():
        if o.get('current_entity_id'):
            voice_entities[o.get('original_voice_id')].add(o['current_entity_id'])
    mixed = set(packet.get('candidate_mixed_clusters', []))
    corrections = sorted((u for u in old_obs if linked(u) and (
        not observations[u].get('current_entity_id') or
        observations[u].get('original_voice_id') in mixed or
        len(voice_entities[observations[u].get('original_voice_id')]) > 1)), key=rank)[:16]
    boundary = sorted((u for u in old_obs if previous - 30 < observations[u]['end_time'] <= previous),
                      key=lambda u: (-observations[u]['end_time'], u))[:16]
    for eid in corrections + boundary:
        admit(eid)
    visible_obs = new_obs | (selected & old_obs)
    visible_mem = new_mem | (selected & old_mem)
    assembled = attachments(new_obs | new_mem | selected, include_window=True)
    assignment_counts = Counter(o.get('current_entity_id') for o in observations.values())
    visible_voices = {observations[u].get('original_voice_id') for u in visible_obs} - {None}
    visible_faces = {f for e in visible_mem for f in re.findall(r'<(face_\d+)>', memories[e]['raw_text'])}
    characters = {c: dict(native_character_id=e.get('native_character_id'),
        canonical_name=e.get('canonical_name'), aliases=e.get('aliases', []),
        assigned_count=assignment_counts[c],
        voice_ids=sorted(set(e.get('voice_ids', [])) & visible_voices),
        face_ids=sorted(set(e.get('face_ids', [])) & visible_faces),
        anchor_ids=sorted(set(candidates[c]) & selected)) for c, e in sorted(registry.items())}
    assignments = assembled['assignment_evidence']
    relevant = visible_voices | visible_obs | set(registry)
    constraints = [pair for pair in packet.get('cannot_link', []) if set(pair) & relevant]
    view = dict(prompt_format_version=FORMAT_VERSION,
        **{k: packet[k] for k in ('schema_version', 'session_id', 'base_graph_version',
                                  'previous_cutoff', 'current_cutoff')},
        previous_cutoff_clip=previous_clip, current_cutoff_clip=current_clip,
        characters=characters,
        observations=[views[u] for u in sorted(visible_obs, key=lambda u: (observations[u]['start_time'], u))],
        memories=[views[e] for e in sorted(visible_mem)],
        historical_ids=sorted(selected),
        clusters=[dict(voice_id=v, utterance_ids=sorted(u for u in visible_obs
                  if observations[u].get('original_voice_id') == v), possible_mixed=v in mixed)
                  for v in sorted(visible_voices)],
        moss=dict(run_id=run, segments=assembled['moss_segments'], alignments=assembled['alignments']),
        assignment_evidence=assignments, cannot_link=constraints,
        source_gaps=[{k: g[k] for k in ('clip_id', 'reason', 'start_s', 'end_s') if k in g}
                     for g in packet.get('source_gaps', [])
                     if previous_clip < g.get('clip_id', -1) <= current_clip])
    if moss.get('anomalies'):
        view['moss']['quality_warnings'] = dict(Counter(
            a.get('action', 'unspecified_anomaly') for a in moss['anomalies']))
    if moss:
        view['moss'].update(start_s=moss.get('start_s',0),cutoff_s=moss['cutoff_s'])
    # Expose current resolutions only for visible memories, without old decision prose.
    view['references'] = assembled['references']
    view['claim_status'] = assembled['claim_status']
    evidence_ids = visible_obs | visible_mem | {a['evidence_id'] for a in assembled['alignments']} | {
        a['evidence_id'] for a in assignments}
    scope = dict(new_observation_ids=sorted(new_obs),
        historical_observation_ids=sorted(selected & old_obs),
        memory_ids=sorted(str(memories[e]['memory_node_id']) for e in visible_mem),
        voice_ids=sorted(visible_voices), evidence_ids=sorted(evidence_ids),
        entity_ids=sorted(registry))
    report = dict(prompt_format_version=FORMAT_VERSION, bytes=byte_size(view), limit_bytes=packet_bytes,
        full_evidence_bytes=byte_size({k: v for k, v in packet.items() if not k.startswith('_')}),
        section_bytes={k: byte_size(v) for k, v in view.items()},
        historical_bytes=byte_size(attachments(selected)) if selected else 0, history_limit_bytes=history_bytes,
        selected_historical_ids=sorted(selected),
        omitted_context=dict(observations=len(old_obs - selected), memories=len(old_mem - selected)))
    return view, scope, report


def prepare_prompt(packet, directory=None):
    packet.pop('_execution_scope', None)
    view, scope, report = build_prompt_packet(packet,
        history_bytes=int(os.environ.get('CONSOLIDATION_HISTORY_BYTES', HISTORY_BYTES)),
        packet_bytes=int(os.environ.get('CONSOLIDATION_PACKET_BYTES', PACKET_BYTES)))
    if directory is not None:
        from pathlib import Path
        directory = Path(directory)
        write(directory/'prompt_packet.json', view)
        write(directory/'prompt_scope.json', scope)
        write(directory/'prompt_size.json', report)
    if report['bytes'] > report['limit_bytes']:
        raise PromptBudgetError(report)
    packet['_execution_scope'] = scope
    return view
