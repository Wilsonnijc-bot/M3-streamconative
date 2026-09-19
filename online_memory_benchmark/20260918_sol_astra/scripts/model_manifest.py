"""Bind external local model checkpoints to exact content without copying weights."""
from pathlib import Path
from bench_common import ROOT,atomic,sha

if __name__=='__main__':
    paths=[Path('/opt/streammeco/models/camplus/v1.0.0/campplus_cn_en_common.pt')]
    for base in ('/opt/streammeco/models/insightface','/opt/streammeco/run/Mandol/naver','/opt/streammeco/models/MOSS-Transcribe-Diarize'):
        paths.extend(p for p in Path(base).rglob('*') if p.is_file() and '.cache' not in p.parts)
    files={str(p):dict(bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(paths)}
    atomic(ROOT/'configs/model_manifest.json',dict(files=files))
    print('MODEL_MANIFEST',len(files),sum(v['bytes'] for v in files.values()),flush=True)
