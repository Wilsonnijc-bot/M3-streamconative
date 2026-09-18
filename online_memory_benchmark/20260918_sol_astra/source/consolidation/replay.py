"""Read saved committed M3 graphs, never a final graph filtered backwards."""
import re
import hashlib
from collections import Counter, defaultdict
from pathlib import Path
from .common import digest, read, seconds, interval


def transcript_sources(text):
    parts = re.split(r'(?:^| \| )(Deepgram|MAI):\s*', text)
    return {parts[i]: parts[i+1] for i in range(1, len(parts), 2)} or {'unknown': text}


def schedule(segments, period=1200):
    if period <= 0:
        raise ValueError('period must be positive')
    origin = segments[0]['absolute_start_seconds']
    committed = [s for s in segments if s.get('status', 'committed') == 'committed']
    ends = [round(s['absolute_end_seconds'] - origin, 6) for s in committed]
    selected = []
    for target in range(period, int(ends[-1]) + period, period):
        eligible = [end for end in ends if end <= target]
        if eligible and eligible[-1] not in selected:
            selected.append(eligible[-1])
    if ends[-1] not in selected:
        selected.append(ends[-1])
    return selected


def load_replay(root, session_id, requested_cutoff, metadata=None):
    root = Path(root)
    raw = root / 'provenance/raw/gemini'
    metadata = Path(metadata) if metadata else raw / 'results/memory/q10_uncompressed/metadata.json'
    segments = read(metadata)['source_segments']
    origin = segments[0]['absolute_start_seconds']
    segments = [s for s in segments if s['absolute_end_seconds'] - origin <= requested_cutoff + 1e-6
                and s.get('status', 'committed') == 'committed']
    if not segments:
        raise ValueError('no committed segment before cutoff')
    observations, gaps, previous = [], [], {}
    for segment in segments:
        clip = segment['segment_id']
        gp = raw / f'results/clip_audits/clip_{clip}_graph.json'
        graph = read(gp)
        version = 'm3_' + digest(graph)
        current = {str(n['id']): n for n in graph['nodes'] if n['type'] == 'voice'}
        added = defaultdict(list)
        for vid, node in current.items():
            old = previous.get(vid, {}).get('metadata', {}).get('contents', [])
            now = node['metadata']['contents']
            if now[:len(old)] != old:
                raise ValueError('historical voice contents are not append-only')
            for text in now[len(old):]:
                added[text].append('voice_' + vid)
        vp = raw / f'work/intermediate/clip_{clip}_voices.json'
        if not vp.exists():
            alternatives = [root / f'cache/voices/gemini/clip_{clip}_voices.json',
                            root / f'cache/voices/gemini/work/intermediate/clip_{clip}_voices.json']
            vp = next((p for p in alternatives if p.exists()), vp)
        if not vp.exists():
            gaps.append({'clip_id': clip, 'reason': 'missing speech cache'})
            previous = current
            continue
        source_bytes=vp.read_bytes()
        import json
        audio=json.loads(source_bytes)
        source_cache_sha256=hashlib.sha256(source_bytes).hexdigest()
        for index, item in enumerate(audio):
            candidates = sorted(set(added.get(item['asr'], [])))
            # Text duplicate across different voices cannot establish a historical assignment.
            voice = candidates[0] if len(candidates) == 1 else None
            start = round(segment['absolute_start_seconds'] - origin + seconds(item['start_time']), 6)
            end = round(segment['absolute_start_seconds'] - origin + seconds(item['end_time']), 6)
            committed_end = round(segment['absolute_end_seconds'] - origin, 6)
            if end > committed_end + 1e-6 or end <= start:
                gaps.append({'clip_id': clip, 'index': index, 'reason': 'ASR interval outside committed segment'})
                continue
            interval(start, end)
            uid = f'{session_id}/utt_{clip:04d}_{index:04d}'
            observations.append(dict(utterance_id=uid, session_id=session_id, clip_id=clip,
                start_time=start, end_time=end, original_voice_id=voice,
                transcripts=transcript_sources(item['asr']), original_transcript=item['asr'],
                audio_ref=f'{vp.resolve()}#/rows/{index}/audio_segment',
                assignment_run_id=f'{session_id}/online/clip_{clip}', created_graph_version=version,
                original_assignment_evidence={'kind': 'historical_graph_delta', 'candidate_voice_ids': candidates,
                    'assignment_status': 'unique_transcript_delta' if voice else 'ambiguous_or_missing',
                    'scores_status': 'not_recorded', 'source_cache_sha256': source_cache_sha256,
                    'source_graph': str(gp.resolve())}))
        previous = current
    cutoff = round(segments[-1]['absolute_end_seconds'] - origin, 6)
    memories = []
    for node in graph['nodes']:
        if node['type'] not in ('semantic', 'episodic'):
            continue
        clip = node['metadata']['timestamp']
        matches = [s for s in segments if s['segment_id'] == clip]
        if not matches:
            raise ValueError('memory from outside committed prefix')
        memories.append(dict(memory_node_id=str(node['id']), kind=node['type'], clip_id=clip,
            available_at=round(matches[0]['absolute_end_seconds']-origin, 6),
            raw_text='\n'.join(node['metadata']['contents']),
            raw_contents=list(node['metadata']['contents']),
            epistemic_status='model-generated semantic claim' if node['type']=='semantic' else 'model-generated event'))
    return dict(session_id=session_id, source_graph_version=version, graph=graph, observations=observations,
                memories=memories, current_cutoff=cutoff, origin_seconds=origin,
                source_gaps=gaps, source_root=str(root.resolve()), segments=segments)
