"""Two sequential 20-minute Astra rounds, each with an immutable review root."""
import shutil, subprocess, sys
from pathlib import Path
from consolidation.common import read,write
base=Path('consolidation/runs/recall_20')
previous=Path('consolidation/runs/live')
for number in (1,2):
    root=base/f'round_{number}'
    if not (root/'checkpoint_20.json').exists():
        root.mkdir(parents=True,exist_ok=True)
        for rel in ('metadata/prefix_20.json','moss/prefix_20'):
            dest=root/rel
            if not dest.exists():
                dest.parent.mkdir(parents=True,exist_ok=True)
                source=previous/rel
                if source.is_dir():shutil.copytree(source,dest)
                else:shutil.copyfile(source,dest)
        if not (root/'published').exists():shutil.copytree(previous/'published',root/'published')
        subprocess.run([sys.executable,'-u','-m','consolidation.live_run','--minutes','20','--output',str(root)],check=True)
    previous=root
rows=[]
for label,root in [('Baseline',Path('consolidation/runs/live'))]+[(f'Round {i}',base/f'round_{i}') for i in (1,2)]:
    summary=read(root/'checkpoint_20.json');path=Path(summary['path'])
    state=read(path/'state.json');packet=read(path/'evidence.json')
    named=sum(bool(state['entities'][eid]['canonical_name']) for eid in state['assignments'].values())
    rows.append(dict(label=label,assigned=len(state['assignments']),total=len(packet['observations']),named=named,**{'summary':summary}))
write(base/'comparison.json',rows)
lines=['# Recall-oriented 20-minute consolidation','',
       'Two real sequential GPT-6 Astra rounds over the same 1187.92-second prefix. Round 1 starts from the original published 20-minute registry; round 2 reviews round 1. MOSS evidence is reused unchanged.','',
       '| Run | Assigned | Named | Accepted / rejected | Review |','| --- | --- | --- | --- | --- |']
for i,row in enumerate(rows):
    link='[Original](../live/review/20min/README.md)' if i==0 else f'[Exact artifacts](round_{i}/review/20min/README.md)'
    s=row['summary'];lines.append(f"| {row['label']} | {row['assigned']}/{row['total']} ({row['assigned']/row['total']:.1%}) | {row['named']} | {s['accepted']} / {s['rejected']} | {link} |")
lines.extend(['','Coverage measures assignment, not identity accuracy. There is no independent identity gold set. Confidence values are model estimates. Full raw evidence, model input/output and updated graph are retained per round.'])
(base/'README.md').write_text('\n'.join(lines)+'\n')
print('TWO_ROUNDS_COMPLETE',flush=True)
