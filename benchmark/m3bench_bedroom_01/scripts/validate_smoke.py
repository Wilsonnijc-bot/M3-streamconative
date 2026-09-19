import os,json
from pathlib import Path
root=Path(os.environ['RUN'])/'smoke';results=root/'results'
files={'A':'method_A_normal_streammeco.jsonl','B':'method_B_streammeco_oneshot.jsonl','C':'method_C_compressed_oneshot.jsonl','D':'method_D_mandol.jsonl'}
summary={}
for method,name in files.items():
 rows=[json.loads(x) for x in (results/name).read_text().splitlines() if x.strip()]
 assert len(rows)==1 and rows[0]['prediction'].strip()
 row=rows[0];assert row['latency_mode']=='warm_retrieval_uncached_question'
 assert row['question']['question']=='What activity is visible in the observed scene?'
 if method!='A':assert row['retrieval_round_count']==1
 assert row['retrieval_round_count']>0
 if method=='D':
  r=row['retrieval_rounds'][0]['retrieval'];assert r['warm_engine']
  assert {x['method'] for x in r['backend_calls']}=={'bm25','cosine_similarity','splade'}
  manifest=json.loads((results/'mandol_adapted/q01/graph/m3_adapter_manifest.json').read_text())
  assert manifest['source_embedding']['vectors_imported'] is False
  assert manifest['source_embedding']['dimension']==3072
  assert manifest['mandol_embedding']['dimension']==1024
 else:
  assert all(r['embedding']['model']=='openai/text-embedding-3-large' for r in row['retrieval_rounds'])
 summary[method]={'retrieval_rounds':row['retrieval_round_count'],'answer':row['prediction'],'warm':True}
(root/'passed.json').write_text(json.dumps({'status':'passed','methods':summary},indent=2)+'\n')
print('ALL_FOUR_METHODS_SMOKE_PASSED',flush=True)
