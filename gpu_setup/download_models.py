#!/usr/bin/env python3
"""Fetch the mandatory CAM++ checkpoint and complete Buffalo-L model pack."""
import argparse
import hashlib
import io
import json
import urllib.request
import zipfile
from pathlib import Path

CAM_BASE = 'https://modelscope.cn/api/v1/models/iic/speech_campplus_sv_zh_en_16k-common_advanced/repo'
CAM_SHA = '92f29b94e6948786a26778c9e302525d185bb08c8b9f5252ed98776902840199'
ZIP_URL = 'https://github.com/deepinsight/insightface/releases/download/v0.7/buffalo_l.zip'
ZIP_SIZE = 275951529

def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(8 << 20), b''): h.update(block)
    return h.hexdigest()

def fetch(url, path, expected=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and (expected is None or digest(path) == expected): return
    tmp = path.with_suffix(path.suffix + '.part')
    with urllib.request.urlopen(url, timeout=180) as src, tmp.open('wb') as dst:
        while block := src.read(1 << 20): dst.write(block)
    if expected and digest(tmp) != expected:
        raise RuntimeError(f'SHA256 mismatch: {path.name}')
    tmp.replace(path)

class RangeZIP(io.RawIOBase):
    """Read selected ZIP members without transferring unrelated model weights."""
    def __init__(self, url, size): self.url, self.size, self.pos = url, size, 0
    def seekable(self): return True
    def readable(self): return True
    def tell(self): return self.pos
    def seek(self, offset, whence=0):
        self.pos = offset + (self.pos if whence == 1 else self.size if whence == 2 else 0)
        if self.pos < 0: raise ValueError('negative seek')
        return self.pos
    def read(self, size=-1):
        end = self.size if size < 0 else min(self.size, self.pos + size)
        if end <= self.pos: return b''
        start = self.pos
        req = urllib.request.Request(self.url, headers={'Range': f'bytes={start}-{end-1}'})
        with urllib.request.urlopen(req, timeout=180) as r:
            if r.status != 206 or r.headers.get('Content-Range') != f'bytes {start}-{end-1}/{self.size}':
                raise RuntimeError('Server did not honor byte range; refusing full-pack download')
            data = r.read()
        if len(data) != end-start: raise IOError('Short range response')
        self.pos = end
        return data

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', type=Path, required=True)
    ap.add_argument('--only', choices=['all','cam','face'], default='all')
    a = ap.parse_args(); root = a.root.resolve(); records = []
    if a.only in ('all','cam'):
        path = root/'models/camplus/v1.0.0/campplus_cn_en_common.pt'
        fetch(CAM_BASE + '?Revision=v1.0.0&FilePath=campplus_cn_en_common.pt', path, CAM_SHA)
        records.append({'path':str(path), 'bytes':path.stat().st_size, 'sha256':digest(path), 'revision':'v1.0.0', 'source':CAM_BASE})
        fetch(CAM_BASE + '?Revision=v1.0.0&FilePath=examples/speaker1_a_cn_16k.wav', root/'fixtures/speaker1.wav', '5f20ce0ddc378ca3239d3ce864b1142726a46a1221ae553912e4e142045df58b')
    if a.only in ('all','face'):
        target = root/'models/insightface/models/buffalo_l'; target.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(RangeZIP(ZIP_URL, ZIP_SIZE)) as z:
            names = {Path(n).name:n for n in z.namelist()}
            for name in ('1k3d68.onnx', '2d106det.onnx', 'det_10g.onnx', 'genderage.onnx', 'w600k_r50.onnx'):
                p = target/name; info = z.getinfo(names[name])
                if not p.exists() or p.stat().st_size != info.file_size:
                    # ZipFile validates each extracted member with its stored CRC32.
                    data = z.read(info)
                    tmp=p.with_suffix('.part'); tmp.write_bytes(data); tmp.replace(p)
                records.append({'path':str(p), 'bytes':p.stat().st_size,'sha256':digest(p),'release':'v0.7','pack':'buffalo_l','source':ZIP_URL})
    root.mkdir(parents=True, exist_ok=True)
    report=root/f'download-{a.only}.json'; report.write_text(json.dumps(records,indent=2)+'\n')
    print(json.dumps(records,indent=2))

if __name__ == '__main__': main()
