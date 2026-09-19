from pathlib import Path
import fcntl,json,os
root=Path(__file__).resolve().parents[3]
old='qwen_thinking';archive='qwen_thinking_baseline'
with (root/'provenance/.render.lock').open('w') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 source=root/'provenance/raw'/old
 if not (root/'provenance/raw'/archive).exists():
  pairs=[(source,root/'provenance/raw'/archive),(root/'results'/old,root/'smoke_tests'/archive),(root/'scripts/runs'/old,root/'scripts/runs'/archive),(root/'provenance/vlm_outputs'/old,root/'provenance/vlm_outputs'/archive)]
  pairs += [(root/'cache'/kind/old,root/'cache'/kind/archive) for kind in ['asr','faces','voices','media','graphs','dependencies']]
  for a,b in pairs:
   if a.exists() or a.is_symlink():
    assert not b.exists();b.parent.mkdir(parents=True,exist_ok=True);a.rename(b)
  for a,b in pairs:
   if not b.exists() or b.is_symlink():continue
   for p in b.rglob('*'):
    if p.is_symlink():
     original=os.readlink(p);target=original.replace('/'+old+'/', '/'+archive+'/')
     if target!=original:p.unlink();p.symlink_to(target)
 p=root/'scripts/sync_run.py';t=p.read_text();t=t.replace("'qwen_thinking':'egolife_10q_qwen35_4b_fps2_thinking'", "'qwen_thinking':'egolife_10q_qwen35_4b_fps2_thinking_ids_v2_full','qwen_thinking_baseline':'egolife_10q_qwen35_4b_fps2_thinking'");p.write_text(t)
 p=root/'scripts/render_results.py';t=p.read_text();t=t.replace("'qwen_thinking':'Qwen3.5 4B thinking — first ten questions'", "'qwen_thinking':'Qwen3.5 4B thinking + identity prompt — first ten questions','qwen_thinking_baseline':'Qwen3.5 4B thinking — baseline prompt preflight'");p.write_text(t)
 p=root/'scripts/organize_results.py';t=p.read_text().replace("'egolife_10q_qwen35_4b_fps2_thinking_20260914':'qwen_thinking'", "'egolife_10q_qwen35_4b_fps2_thinking_20260914':'qwen_thinking_baseline'");p.write_text(t)
 p=root/'provenance/relocations.json';d=json.loads(p.read_text());d['egolife_10q_qwen35_4b_fps2_thinking_20260914']='provenance/raw/qwen_thinking_baseline';d['qwen_thinking_selected_full_run']='provenance/raw/qwen_thinking';p.write_text(json.dumps(d,indent=2)+'\n')
print('Canonical Qwen result route updated; prior baseline retained separately.')
