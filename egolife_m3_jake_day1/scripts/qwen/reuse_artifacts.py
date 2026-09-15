"""Copy only successful provider caches with verified content-addressed identity."""
import os,json,hashlib,shutil
from pathlib import Path
run=Path(os.environ['QWEN_RUN']);source=Path('/opt/streammeco/run/egolife_10q_gemini')
dest=run/'results/asr_cache';dest.mkdir(parents=True,exist_ok=True)
config=json.loads((Path(os.environ['STREAMMECO_ROOT'])/'configs/api_config.json').read_text())
rows=[]
cache_sources=[source/'results/asr_cache',Path('/opt/streammeco/run/egolife_10q_qwen35_4b_fps2/results/asr_cache')]
for p in [p for cache_source in cache_sources for p in cache_source.glob('*.json')]:
 saved=json.loads(p.read_text());provider=saved['provider'];settings={k:v for k,v in config[provider].items() if k not in {'api_key','api_key_env'}}
 expected=hashlib.sha256(json.dumps([provider,'wav',settings,saved['audio_sha256']],sort_keys=True).encode()).hexdigest()
 if p.stem!=expected:raise RuntimeError('Cache configuration mismatch '+p.name)
 assert isinstance(saved['segments'],list)
 shutil.copy2(p,dest/p.name)
 rows.append({'file':p.name,'source':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'provider':provider,'audio_sha256':saved['audio_sha256'],'configuration_verified':True})
(run/'results/cache_provenance.json').write_text(json.dumps(rows,indent=2)+'\n')
shutil.copy2(source/'results/asr_calls.jsonl',run/'results/original_asr_acquisition.jsonl')
# Exact previously cut media are independent of the generated graph. Identity caches are excluded.
committed=[json.loads(line) for line in (source/'results/segment_schedule_events.jsonl').read_text().splitlines() if line.strip()]
media_dest=run/'work/segments';media_dest.mkdir(parents=True,exist_ok=True)
for row in committed:
 p=source/'work/segments'/f"segment_{row['segment_id']:04d}.mp4"
 if p.exists():shutil.copy2(p,media_dest/p.name)
print('REUSED_SUCCESSFUL_ASR_CACHES',len(rows),flush=True)
