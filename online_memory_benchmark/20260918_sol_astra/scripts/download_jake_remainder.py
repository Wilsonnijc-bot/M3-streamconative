"""Fetch missing original Day 1 recordings at a pinned upstream revision."""
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path
import urllib.request
from bench_common import ROOT,read,sha,atomic

def main():
    inventory=read(ROOT/'assets/questions/jake_day1_inventory.json')
    folder=ROOT/'media/jake';folder.mkdir(parents=True,exist_ok=True)
    def fetch(row):
        path=folder/Path(row['path']).name;expected=row['lfs']['oid']
        if path.exists() and path.stat().st_size==row['size'] and sha(path)==expected:return path.name
        url=f"https://huggingface.co/datasets/{inventory['repo']}/resolve/{inventory['revision']}/{row['path']}"
        temporary=path.with_suffix('.download')
        with urllib.request.urlopen(url,timeout=120) as response,temporary.open('wb') as out:
            for chunk in iter(lambda:response.read(1024*1024),b''):out.write(chunk)
        if temporary.stat().st_size!=row['size'] or sha(temporary)!=expected:raise ValueError('source checksum mismatch: '+path.name)
        temporary.replace(path);return path.name
    with ThreadPoolExecutor(max_workers=4) as pool:
        for count,future in enumerate(as_completed([pool.submit(fetch,r) for r in inventory['missing_files']]),1):
            print('DOWNLOADED',count,future.result(),flush=True)
    atomic(ROOT/'metadata/jake_download.json',dict(revision=inventory['revision'],verified_files=len(inventory['missing_files']),bytes=sum(r['size'] for r in inventory['missing_files'])))
if __name__=='__main__':main()
