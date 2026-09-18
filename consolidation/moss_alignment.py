from collections import Counter, defaultdict
from .common import interval


def align(observations, moss, session_id, cutoff):
    if moss is None:
        return [], {}, []
    if moss['session_id'] != session_id or abs(moss['cutoff_s']-cutoff)>1e-6:
        raise ValueError('MOSS session/prefix mismatch')
    run = moss['run_id']
    segments = moss['segments']
    for s in segments:
        interval(s['start'], s['end'], cutoff)
    records, counts = [], defaultdict(Counter)
    for o in observations:
        overlaps = defaultdict(float)
        for s in segments:
            overlap = min(s['end'], o['end_time']) - max(s['start'], o['start_time'])
            if overlap > 0:
                overlaps[f"{run}/{s['speaker']}"] += overlap
        status = 'aligned' if len(overlaps)==1 else 'ambiguous' if overlaps else 'unmatched'
        record = dict(evidence_id='alignment/'+o['utterance_id']+'/'+run,
            kind='moss_alignment', session_id=session_id, available_at=cutoff,
            utterance_id=o['utterance_id'], original_voice_id=o['original_voice_id'],
            alignment_status=status, overlaps=dict(overlaps), speaker=next(iter(overlaps)) if status=='aligned' else None)
        records.append(record)
        counts[o['original_voice_id'] or 'unknown'][record['speaker'] or status] += 1
    summaries = {v:dict(c) for v,c in counts.items()}
    mixed = [v for v,c in counts.items() if len([s for s in c if s not in ('ambiguous','unmatched')])>1]
    return records, summaries, mixed
