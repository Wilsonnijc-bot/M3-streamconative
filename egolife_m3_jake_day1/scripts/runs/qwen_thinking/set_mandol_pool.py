from pathlib import Path
import json,hashlib,ast,argparse,sys,datetime
r=Path('/opt/streammeco/run/egolife_10q_qwen35_4b_fps2_thinking_ids_v2_full')
p=r/'code/Mandol/benchmarks/egolife_m3_first10.py'
assert not (r/'results/method_D_mandol.jsonl').exists(),'Method D has already produced results; cannot mix configurations'
t=p.read_text();before=hashlib.sha256(t.encode()).hexdigest()
d=r/'lineage/mandol_pool_100_final_20';d.mkdir(parents=True,exist_ok=True)
if not (d/p.name).exists():(d/p.name).write_text(t)
a='parser.add_argument("--top-k", type=int, default=2)';b='parser.add_argument("--candidate-k", type=int, default=20)'
assert a in t and b in t
t=t.replace(a,'parser.add_argument("--top-k", type=int, default=20)').replace(b,'parser.add_argument("--candidate-k", type=int, default=100)')
t=t.replace('"top_k": args.top_k,','"top_k": args.top_k,\n                "candidate_k": args.candidate_k,')
# Validate actual CLI parsing without loading retrieval models or consuming GPU.
tree=ast.parse(t);fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='parse_args')
namespace={'argparse':argparse,'Path':Path};exec(compile(ast.Module(body=[fn],type_ignores=[]),str(p),'exec'),namespace)
sys.argv=['mandol','eval','--qa','qa.json','--results','results'];args=namespace['parse_args']()
assert args.candidate_k==100 and args.top_k==20
p.write_text(t)
record={'updated_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'method':'D','backend':'Mandol','candidate_pool':100,'final_results':20,'selection':'BM25+dense+SPLADE, RRF fusion, up to 100 candidates passed to reranker, top 20 returned (bounded by available evidence)','applies_to':'upcoming Qwen full-run Method D and its warmup probe','previous_candidate_pool':20,'previous_final_results':2,'existing_method_D_rows':0,'previous_code_sha256':before,'code_sha256':hashlib.sha256(t.encode()).hexdigest(),'effective_cli_verified':True}
(r/'results/mandol_retrieval_config.json').write_text(json.dumps(record,indent=2)+'\n')
(d/'configuration.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record))
