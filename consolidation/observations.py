"""Append-only, session-scoped observation store. Alternate ASRs share one record."""
import fcntl
import json
from pathlib import Path
from .common import dumps, interval


class ObservationLedger:
    def __init__(self, path, session_id):
        self.path, self.session_id = Path(path), session_id

    def append(self, observations):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open('a+') as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            handle.seek(0)
            existing = {x['utterance_id']: x for x in map(json.loads, handle)}
            if any(item['session_id'] != self.session_id for item in existing.values()):
                raise ValueError('ledger session mismatch')
            pending = []
            for item in observations:
                interval(item['start_time'], item['end_time'])
                if item['session_id'] != self.session_id:
                    raise ValueError('ledger session mismatch')
                uid = item['utterance_id']
                if uid in existing and existing[uid] != item:
                    raise ValueError('immutable observation changed: ' + uid)
                if uid not in existing:
                    pending.append(item)
                    existing[uid] = item
            handle.seek(0, 2)
            for item in pending:
                handle.write(dumps(item) + '\n')
            handle.flush()
            import os
            os.fsync(handle.fileno())

    def load(self):
        if not self.path.exists():
            return []
        records = [json.loads(line) for line in self.path.read_text().splitlines()]
        if any(x['session_id'] != self.session_id for x in records):
            raise ValueError('ledger session mismatch')
        return records
