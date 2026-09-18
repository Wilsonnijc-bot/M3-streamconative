from collections import Counter, defaultdict
from .common import interval


def validate_window(moss, session_id, start_s, cutoff):
    interval(start_s,cutoff)
    interval(moss.get('start_s',0),moss['cutoff_s'])
    if (moss['session_id'] != session_id or abs(moss['cutoff_s']-cutoff)>1e-6
            or abs(moss.get('start_s',0)-start_s)>1e-6):
        raise ValueError('MOSS session/window mismatch')
    if moss.get('timestamp_origin','session') != 'session':
        raise ValueError('MOSS timestamps must be normalized to session time')
    for s in moss['segments']:
        interval(s['start'], s['end'], cutoff)
        if s['start'] < start_s or not s.get('speaker'):
            raise ValueError('MOSS segment outside window or missing speaker')


def align(observations, moss, session_id, cutoff, start_s=0):
    if moss is None:
        return [], {}, []
    validate_window(moss,session_id,start_s,cutoff)
    run = moss['run_id']
    segments = moss['segments']
    records, counts = [], defaultdict(Counter)
    for o in observations:
        if o['end_time'] <= start_s:
            continue  # Historical anchors were not included in this audio window.
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
