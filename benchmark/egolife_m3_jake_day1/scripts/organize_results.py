"""Idempotent grouping of local experiment artifacts; model runs stay remote."""
from pathlib import Path
import json,os,hashlib,shutil,time
ROOT=Path(__file__).resolve().parents[1]
CASES={
'egolife_10q_gemini_20260914':'gemini',
'egolife_10q_qwen35_4b_fps2_20260914':'qwen_non_thinking',
'egolife_10q_qwen35_4b_fps2_thinking_20260914':'qwen_thinking_baseline',
'egolife_10q_qwen35_4b_fps2_thinking_ids_v2_20260914':'qwen_identity_v2',
'first_clip_vlm_compare_hyperstack_20260914T052138Z':'first_clip_hyperstack',
'first_clip_vlm_compare_openrouter_20260914':'first_clip_openrouter',
'gemini_preflight_review_20260914':'gemini_preflight',
'gemini38':'gemini_request',
}

def move(src,dst):
    dst.parent.mkdir(parents=True,exist_ok=True)
    if dst.exists() or dst.is_symlink():
        raise RuntimeError(f'Destination already exists: {dst}')
    src.rename(dst)

def relocate_file(src,dst):
    """Preserve internal references with a relative link at the raw provenance path."""
    if src.is_symlink():return
    dst.parent.mkdir(parents=True,exist_ok=True)
    if dst.exists():
        if hashlib.sha256(src.read_bytes()).digest()!=hashlib.sha256(dst.read_bytes()).digest():
            dst=dst.with_name(dst.stem+'_'+hashlib.sha256(src.read_bytes()).hexdigest()[:10]+dst.suffix)
        else:
            src.unlink();src.symlink_to(os.path.relpath(dst,src.parent));return
    src.rename(dst);src.symlink_to(os.path.relpath(dst,src.parent))

def organize():
    for name in ['scripts','cache','provenance/reference_data','results','provenance/raw']:(ROOT/name).mkdir(parents=True,exist_ok=True)
    for kind in ['asr','faces','voices','media','graphs','dependencies']:(ROOT/'cache'/kind).mkdir(exist_ok=True)
    manifest=ROOT/'provenance/relocations.json'
    records=json.loads(manifest.read_text()) if manifest.exists() else {}
    for old,case in CASES.items():
        src=ROOT/old;dest=ROOT/'provenance/raw'/case
        if src.exists() and not dest.exists():
            records[old]=str(dest.relative_to(ROOT));move(src,dest)
        elif src.exists():
            raise RuntimeError(f'Old producer recreated {src}; update it before merging')
    for name in ['EgoLifeQA_A1_JAKE.json','first_question.json']:
        if (ROOT/name).exists():move(ROOT/name,ROOT/'provenance/reference_data'/name);records[name]='provenance/reference_data/'+name
    for name in ['memory','predictions','qwen_smoke_record.json']:
        if (ROOT/name).exists():move(ROOT/name,ROOT/'provenance/raw/legacy_smoke'/name);records[name]='provenance/raw/legacy_smoke/'+name
    for run in sorted((ROOT/'provenance/raw').iterdir()):
        if not run.is_dir():continue
        # Vendored dependencies are cache data, not experiment runner scripts.
        deps=run/'test_deps'
        if deps.exists() and not deps.is_symlink():
            dest=ROOT/'cache/dependencies'/run.name
            move(deps,dest);deps.symlink_to(os.path.relpath(dest,deps.parent),target_is_directory=True)
        elif deps.is_symlink():
            target=ROOT/'cache/dependencies/qwen_non_thinking'
            if target.exists():deps.unlink();deps.symlink_to(os.path.relpath(target,deps.parent),target_is_directory=True)
        files=[p for p in run.rglob('*') if p.is_file() and not p.is_symlink()]
        for p in files:
            rel=p.relative_to(run)
            if 'test_deps' in rel.parts:continue
            if p.suffix in {'.sh','.py'}:
                relocate_file(p,ROOT/'scripts/runs'/run.name/rel)
            elif 'asr_cache' in rel.parts:
                k=rel.parts.index('asr_cache');suffix=Path(*rel.parts[:k],*rel.parts[k+1:])
                relocate_file(p,ROOT/'cache/asr'/run.name/suffix)
            elif p.name.endswith('_faces.json'):
                relocate_file(p,ROOT/'cache/faces'/run.name/rel)
            elif p.name.endswith('_voices.json'):
                relocate_file(p,ROOT/'cache/voices'/run.name/rel)
            elif p.name.endswith('_graph.pkl') and 'clip_audits' in rel.parts:
                relocate_file(p,ROOT/'cache/graphs'/run.name/rel)
            elif p.suffix in {'.mp4','.webm','.wav','.mp3'} and 'work' in rel.parts:
                relocate_file(p,ROOT/'cache/media'/run.name/rel)
    manifest.write_text(json.dumps(records,indent=2)+'\n')
    print('ORGANIZED',len(records),'original roots/files')
if __name__=='__main__':organize()
