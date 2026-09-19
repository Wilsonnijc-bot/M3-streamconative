import hashlib
import json
import math
import os
import tempfile
from pathlib import Path


def dumps(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)


def digest(value):
    return hashlib.sha256(dumps(value).encode()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix='.write-')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            handle.write(dumps(value) + '\n')
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def seconds(value):
    if isinstance(value, (float, int)):
        return float(value)
    result = 0.0
    for part in value.split(':'):
        result = result * 60 + float(part)
    return result


def interval(start, end, cutoff=None):
    if not all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in (start, end)):
        raise ValueError('timestamps must be finite numbers')
    if start < 0 or end <= start or (cutoff is not None and end > cutoff + 1e-6):
        raise ValueError('invalid or future interval')
