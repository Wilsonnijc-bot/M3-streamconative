"""Resolve a complete immutable M3/Mandol publication through its CURRENT pointer."""
import hashlib
import json
from pathlib import Path
import re


def current_version(root):
    version = json.loads((Path(root)/'CURRENT.json').read_text())['version']
    if not re.fullmatch(r'v_[0-9a-f]{64}', version):
        raise ValueError('invalid consolidation version')
    return version


def resolve_bundle(root):
    root = Path(root)
    version = current_version(root)
    location = root/'versions'/version
    ready = json.loads((location/'retrieval_ready.json').read_text())
    manifest = json.loads((location/'manifest.json').read_text())
    if (ready.get('status') != 'ready' or ready.get('graph_version') != version
            or manifest.get('version') != version or not manifest.get('retrieval_complete')):
        raise ValueError('consolidation retrieval bundle is incomplete')
    for name, expected in manifest['sha256'].items():
        path = location/name
        if (Path(name).is_absolute() or '..' in Path(name).parts
                or not path.is_file() or path.is_symlink()
                or hashlib.sha256(path.read_bytes()).hexdigest() != expected):
            raise ValueError('consolidation retrieval bundle integrity failure')
    if ready['mandol_graph'] != 'mandol' or ready['native_graph'] != 'graph.pkl':
        raise ValueError('unexpected retrieval bundle paths')
    return version, location/'mandol'
