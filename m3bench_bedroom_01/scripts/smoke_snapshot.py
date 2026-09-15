"""Fork the first committed segment for a neutral all-method functional check."""
import os,sys,json,pickle
from pathlib import Path
sys.path.insert(0,os.environ['STREAMMECO_ROOT'])
from benchmarks.bedroom_benchmark import save_snapshot
run=Path(os.environ['RUN']);smoke=run/'smoke';smoke.mkdir(exist_ok=True)
with (run/'work/build_state.pkl').open('rb') as h:state=pickle.load(h)
assert len(state['completed'])==1
assert state['segment_map'][1].get('status','committed')=='committed'
rows=[{'ID':f'Q{i:02d}','query_time':{'date':'VIDEO','time':30.0},'question':'What activity is visible in the observed scene?','answer':'Functional check only; not benchmark scoring'} for i in range(1,16)]
(smoke/'questions.json').write_text(json.dumps(rows,indent=2)+'\n')
save_snapshot(state['graph'],rows[0],1,state['segment_map'],smoke/'results')
