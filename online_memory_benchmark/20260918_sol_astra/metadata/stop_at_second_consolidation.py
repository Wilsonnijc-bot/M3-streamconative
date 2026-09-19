"""External run observer: pause the process tree after the 40-minute Sol submission."""
import json
import argparse
import os
from pathlib import Path
import signal
import time

ROOT=Path('/opt/streammeco/run/online_memory_benchmark/20260918_sol_astra')
parser=argparse.ArgumentParser()
parser.add_argument('--pid',type=int,required=True)
parser.add_argument('--results',required=True)
args=parser.parse_args()
PID=args.pid
RESULTS=(ROOT/args.results).resolve()
assert RESULTS.is_relative_to(ROOT)
STATUS=ROOT/'metadata/stop_at_second_consolidation.json'


def save(**values):
    record=dict(target_media_seconds=2400,interpretation='second scheduled 20-minute cycle',
                worker_pid=PID,results=str(RESULTS),observed_unix=time.time(),**values)
    temp=STATUS.with_suffix('.tmp')
    temp.write_text(json.dumps(record,indent=2)+'\n')
    temp.replace(STATUS)
    print(json.dumps(record),flush=True)


def identity(pid):
    return Path(f'/proc/{pid}/stat').read_text().split(') ',1)[1].split()[19]


def children(pid):
    result=[]
    for task in Path(f'/proc/{pid}/task').glob('*/children'):
        try:result.extend(int(x) for x in task.read_text().split())
        except FileNotFoundError:pass
    return sorted(set(result))


start=identity(PID)
assert 'scripts/online_benchmark.py' in Path(f'/proc/{PID}/cmdline').read_bytes().decode().split('\0')
save(status='armed')
while True:
    try:
        if identity(PID)!=start:raise ProcessLookupError('worker PID was reused')
    except (FileNotFoundError,ProcessLookupError):
        save(status='worker_exited_before_trigger')
        break
    matches=[]
    for snapshot in (RESULTS/'jake').glob('C*/consolidation/snapshot_*/snapshot.json'):
        receipt=snapshot.parent/'response_status.json'
        if not receipt.exists():continue
        try:
            state=json.loads(snapshot.read_text())
            response=json.loads(receipt.read_text())
        except (json.JSONDecodeError,FileNotFoundError):continue
        if state['cutoff_timestamp']>=2400 and response.get('response_id'):
            matches.append((snapshot,response,state))
    if matches:
        # Stop the parent first so it cannot launch another child while freezing.
        pending=[PID];stopped=[]
        while pending:
            pid=pending.pop()
            if pid in stopped:continue
            try:
                os.kill(pid,signal.SIGSTOP)
                stopped.append(pid)
                pending.extend(children(pid))
            except ProcessLookupError:pass
        snapshot,response,state=sorted(matches,key=lambda x:str(x[0]))[0]
        save(status='paused',signal='SIGSTOP',stopped_pids=stopped,
             trigger_snapshot=str(snapshot),response=response,
             actual_cutoff=state['cutoff_timestamp'],
             note='Remote background API request may finish; local benchmark processing is suspended.')
        break
    time.sleep(0.2)
