"""Validate OpenRouter Qwen retrieval endpoints without exposing credentials."""
import json,os,time,math
from pathlib import Path
import httpx

root=Path(os.environ['RUN'])/'provenance/provider_probe'
root.mkdir(parents=True,exist_ok=True)
key=os.environ['OPENROUTER_API_KEY']
tests=[('embedding','embeddings',{'model':'qwen/qwen3-embedding-0.6b','input':['A cup of coffee is on the desk.','A red coat hangs by the door.'],'encoding_format':'float'}),
       ('rerank','rerank',{'model':'qwen/qwen3-reranker-0.6b','query':'Where is the coffee?','documents':['A cup of coffee is on the desk.','A red coat hangs by the door.'],'top_n':2,'return_documents':False})]
results=[]
with httpx.Client(timeout=120,trust_env=False) as client:
 for name,endpoint,payload in tests:
  start=time.time();clock=time.perf_counter()
  try:
   response=client.post('https://openrouter.ai/api/v1/'+endpoint,headers={'Authorization':'Bearer '+key},json=payload)
   try:body=response.json()
   except ValueError:body={'error':response.text[:300]}
   result={'test':name,'model':payload['model'],'http_status':response.status_code,'request_start':start,'request_end':time.time(),'latency_ms':(time.perf_counter()-clock)*1000,'passed':False}
   if name=='embedding' and response.is_success:
    vectors=body.get('data',[])
    result.update(returned_model=body.get('model'),dimensions=[len(v['embedding']) for v in vectors],usage=body.get('usage'))
    result['passed']=len(vectors)==2 and all(len(v['embedding'])==1024 and all(math.isfinite(x) for x in v['embedding']) for v in vectors)
   elif name=='rerank' and response.is_success:
    result.update(response=body);rows=body.get('results',body.get('data',[]));result['passed']=len(rows)==2 and {v['index'] for v in rows}=={0,1}
   else:result['response']=body
  except Exception as exc:result={'test':name,'passed':False,'error':type(exc).__name__+': '+str(exc)}
  results.append(result);print(json.dumps(result),flush=True)
(root/'openrouter.json').write_text(json.dumps(results,indent=2)+'\n')
raise SystemExit(0 if all(x['passed'] for x in results) else 1)
