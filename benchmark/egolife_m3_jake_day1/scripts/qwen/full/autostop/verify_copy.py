"""Verify the completed copy, then hibernate the Hyperstack VM."""
import datetime,fcntl,hashlib,json,os,subprocess,time,sys,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
RAW=ROOT/'provenance/raw/qwen_thinking'
REMOTE='/opt/streammeco/run/egolife_10q_qwen35_4b_fps2_thinking_ids_v2_full'
SSH=['ssh','-i','/Users/nijiachen/.ssh/streammeco_hyperstack_1042997','-o','BatchMode=yes','-o','ConnectTimeout=15','ubuntu@185.216.21.158']
API='https://infrahub-api.nexgencloud.com/v1'
VM_ID=1042997
def api_key():
 key=os.environ.get('HYPERSTACK_API_KEY','').strip()
 if key:return key
 result=subprocess.run(['security','find-generic-password','-s','StreamMeCo-Hyperstack','-a','api_key','-w'],capture_output=True,text=True)
 return result.stdout.strip() if result.returncode==0 else ''
def request(path,key):
 req=urllib.request.Request(API+path,headers={'accept':'application/json','api_key':key})
 with urllib.request.urlopen(req,timeout=30) as response:return json.load(response)
def vm_status(payload):
 instance=payload.get('instance') or payload.get('virtual_machine') or payload
 return str(instance.get('status','')).upper()
def hibernate():
 key=api_key()
 if not key:raise RuntimeError('HYPERSTACK_API_KEY is unavailable; hibernation has not been requested')
 request(f'/core/virtual-machines/{VM_ID}/hibernate?retain_ip=false',key)
 deadline=time.monotonic()+1800
 while time.monotonic()<deadline:
  status=vm_status(request(f'/core/virtual-machines/{VM_ID}',key))
  print('HYPERSTACK_STATUS '+status,flush=True)
  if status=='HIBERNATED':return
  if status not in {'ACTIVE','HIBERNATING'}:raise RuntimeError('Unexpected Hyperstack VM status: '+status)
  time.sleep(15)
 raise RuntimeError('Timed out waiting for HIBERNATED status')
def main():
 RAW.mkdir(parents=True,exist_ok=True)
 with (RAW/'.auto_stop_copy.lock').open('w') as lock:
  try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  except BlockingIOError:return
  while True:
   try:
    result=subprocess.run(SSH+['cat '+REMOTE+'/shutdown_ready_manifest.json'],capture_output=True,text=True,timeout=30)
    if result.returncode:time.sleep(30);continue
    manifest=json.loads(result.stdout)
    subprocess.run([sys.executable,str(ROOT/'scripts/sync_run.py'),'qwen_thinking'],check=True)
    for name,expected in manifest['files'].items():
     p=RAW/name
     if hashlib.sha256(p.read_bytes()).hexdigest()!=expected:raise RuntimeError('Copy checksum mismatch: '+name)
    receipt={'instance_id':1042997,'manifest_sha256':manifest['manifest_sha256'],'verified_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'verified_files':len(manifest['files']),'local_root':str(RAW)}
    p=RAW/'shutdown_copy_verified.json';p.write_text(json.dumps(receipt,indent=2)+'\n')
    subprocess.run(SSH+['cat > '+REMOTE+'/shutdown_copy_verified.json'],input=p.read_text(),text=True,check=True)
    print('VERIFIED_COPY_ACKNOWLEDGED '+json.dumps(receipt),flush=True)
    hibernate()
    print('HIBERNATED instance_id=1042997',flush=True);return
   except Exception as e:
    print('WAITING '+str(e),flush=True);time.sleep(30)
if __name__=='__main__':main()
