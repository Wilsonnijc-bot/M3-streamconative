"""A full launch requires inspected real prefix receipts, not just a tmux shell."""
from pathlib import Path
from bench_common import ROOT,read,sha

def main():
    gate=read(ROOT/'metadata/validation_gate.json')
    assert gate['status']=='passed'
    for relative,h in gate['validated_source_sha256'].items():assert sha(ROOT/relative)==h,relative
    for relative,h in gate['evidence_sha256'].items():assert sha(ROOT/relative)==h,relative
    assert read(ROOT/'metadata/readiness.json')['status']=='ready'
    print('LAUNCH_GATE_PASS',flush=True)
if __name__=='__main__':main()
