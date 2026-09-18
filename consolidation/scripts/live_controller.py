"""Monitor the authorized Hyperstack job and consolidate each completed prefix."""
import subprocess
import sys
import time
from pathlib import Path

HOST='ubuntu@38.80.122.150'
KEY='/Users/nijiachen/.ssh/streammeco_hyperstack_1042997'
REMOTE='/opt/streammeco/run/consolidation_live'
ROOT=Path('consolidation/runs/live')
SSH=['ssh','-o','BatchMode=yes','-o','ConnectTimeout=15','-i',KEY,HOST]


def main():
    for minutes in (20,40):
        if (ROOT/f'checkpoint_{minutes}.json').exists():
            print('ALREADY_PUBLISHED',minutes,flush=True)
            continue
        remote=REMOTE+f'/results/prefix_{minutes}'
        deadline=time.monotonic()+7200
        while True:
            status=subprocess.run(SSH+[f'test -s {remote}/moss.json && echo READY; if test -f {REMOTE}/exit_status.txt; then cat {REMOTE}/exit_status.txt; fi'],
                capture_output=True,text=True,timeout=30)
            if 'READY' in status.stdout:break
            if status.stdout.strip():raise RuntimeError('remote MOSS exited without required prefix artifact: '+status.stdout.strip())
            if time.monotonic()>deadline:raise TimeoutError('MOSS prefix did not finish')
            print('WAITING_MOSS',minutes,flush=True)
            time.sleep(20)
        local=ROOT/f'moss/prefix_{minutes}'
        local.mkdir(parents=True,exist_ok=True)
        subprocess.run(['rsync','-az','--exclude=prefix.wav','--exclude=window.wav','-e','ssh -i '+KEY,HOST+':'+remote+'/',str(local)+'/'],check=True)
        print('MOSS_SYNCED',minutes,flush=True)
        subprocess.run([sys.executable,'-u','-m','consolidation.live_run','--minutes',str(minutes),
                        '--moss-json',str(local/'moss.json')],check=True)
    subprocess.run([sys.executable,'-m','consolidation.render_live'],check=True)
    print('LIVE_CONTROLLER_COMPLETE',flush=True)


if __name__=='__main__':main()
