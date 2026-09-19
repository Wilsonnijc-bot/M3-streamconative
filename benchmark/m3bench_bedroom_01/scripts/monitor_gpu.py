import subprocess,time,re
from pathlib import Path
root=Path('/opt/streammeco/run/m3bench_bedroom_gemini')
with (root/'results/gpu_load.csv').open('a',buffering=1) as f:
 f.write('timestamp, gpu_util_percent, memory_used_MiB, memory_total_MiB\n')
 while True:
  result=subprocess.run(['nvidia-smi','--query-gpu=timestamp,utilization.gpu,memory.used,memory.total','--format=csv,noheader,nounits'],capture_output=True,text=True)
  f.write(result.stdout)
  status=(root/'pipeline_status.txt').read_text() if (root/'pipeline_status.txt').exists() else ''
  if re.search(r'^exit_status=\d+$',status,re.M):break
  time.sleep(30)
