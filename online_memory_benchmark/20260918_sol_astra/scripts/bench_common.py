"""Portable, atomic benchmark records. No credentials are serialized."""
import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REVISION = '0f99f2d0ebe89ac095bcc5903c4dd8f72b367286'

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()

def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()

def read(path):
    return json.loads(Path(path).read_text())

def atomic(path, value, binary=False):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    payload = value if binary else (json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n').encode()
    with tmp.open('wb') as f:
        f.write(payload); f.flush(); os.fsync(f.fileno())
    os.replace(tmp, path)
    fd = os.open(path.parent, os.O_RDONLY)
    try: os.fsync(fd)
    finally: os.close(fd)

def rows(path):
    return [json.loads(x) for x in Path(path).read_text().splitlines() if x.strip()]

def jsonl(path, values):
    atomic(path, ''.join(json.dumps(v, ensure_ascii=False, allow_nan=False) + '\n' for v in values).encode(), True)

def append(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a') as f:
        f.write(json.dumps(value, ensure_ascii=False, allow_nan=False) + '\n'); f.flush(); os.fsync(f.fileno())
