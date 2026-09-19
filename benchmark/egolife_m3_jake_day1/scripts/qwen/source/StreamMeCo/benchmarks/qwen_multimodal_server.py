"""One warmed multimodal checkpoint, serialized GPU requests, separated timings."""
import os, sys, json, time, threading, base64, io, hashlib
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
ROOT=Path(__file__).resolve().parents[1];os.chdir(ROOT);sys.path.insert(0,str(ROOT))
import torch
from PIL import Image
from transformers import AutoModelForMultimodalLM, AutoProcessor
MODEL_ID='Qwen/Qwen3.5-4B'
checkpoint=Path(os.environ['QWEN_MODEL_PATH'])
assert checkpoint.name=='Qwen3.5-4B'
lock=threading.Lock()
started=time.perf_counter()
model=AutoModelForMultimodalLM.from_pretrained(str(checkpoint),torch_dtype='auto',device_map='cuda:0',attn_implementation='sdpa').eval()
processor=AutoProcessor.from_pretrained(str(checkpoint))
model_load_ms=(time.perf_counter()-started)*1000
manifest={'model':MODEL_ID,'checkpoint':str(checkpoint),'dtype':str(model.dtype),'device':str(model.device),'gpu':torch.cuda.get_device_name(0),'torch':torch.__version__,'cuda':torch.version.cuda,'model_load_ms':model_load_ms,'config_sha256':hashlib.sha256((checkpoint/'config.json').read_bytes()).hexdigest(),'revision':'not exposed in installed directory','empty_cache_per_call':False,'serialized_generation':True}
Path(os.environ['QWEN_RUN'],'server_model_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
def generate(payload):
 arrival=time.perf_counter()
 with lock:
  timings={'queue_wait_ms':(time.perf_counter()-arrival)*1000};start=time.perf_counter();messages=[];image_count=0
  for message in payload['messages']:
   content=message['content']
   if isinstance(content,str):content=[{'type':'text','text':content}]
   converted=[]
   for item in content:
    if item['type']=='text':converted.append(item)
    elif item['type']=='image_url':
     uri=item['image_url']['url'];assert uri.startswith('data:image/')
     converted.append({'type':'image','image':Image.open(io.BytesIO(base64.b64decode(uri.split(',',1)[1]))).convert('RGB')});image_count+=1
    else:raise ValueError('Unsupported message content '+item['type'])
   messages.append({'role':message['role'],'content':converted})
  timings['media_preparation_ms']=(time.perf_counter()-start)*1000;start=time.perf_counter()
  inputs=processor.apply_chat_template(messages,tokenize=True,add_generation_prompt=True,enable_thinking=True,return_dict=True,return_tensors='pt')
  timings['processor_tokenization_ms']=(time.perf_counter()-start)*1000
  actual_images=int(inputs['image_grid_thw'].shape[0]) if 'image_grid_thw' in inputs else 0
  assert actual_images==image_count,(actual_images,image_count)
  torch.cuda.synchronize();start=time.perf_counter();inputs=inputs.to(model.device);torch.cuda.synchronize();timings['device_transfer_ms']=(time.perf_counter()-start)*1000
  settings={'max_new_tokens':int(payload.get('max_new_tokens',16384)),'do_sample':False,'repetition_penalty':1.08 if payload.get('purpose')=='memory_construction' else 1.0}
  start=time.perf_counter()
  with torch.inference_mode():generated=model.generate(**inputs,**settings)
  torch.cuda.synchronize();timings['cuda_generation_ms']=(time.perf_counter()-start)*1000;start=time.perf_counter()
  ids=generated[:,inputs.input_ids.shape[1]:];response=processor.batch_decode(ids,skip_special_tokens=True,clean_up_tokenization_spaces=False)[0]
  raw_response=response
  thinking_completed='</think>' in raw_response
  response=raw_response.rsplit('</think>',1)[-1].strip() if thinking_completed else ''
  n=int(ids.shape[1]);input_n=int(inputs.input_ids.shape[1]);timings['decoding_ms']=(time.perf_counter()-start)*1000
  body={'response':response,'raw_response':raw_response,'thinking_enabled':True,'thinking_completed':thinking_completed,'model':MODEL_ID,'returned_model':MODEL_ID,'input_tokens':input_n,'output_tokens':n,'total_tokens':input_n+n,'finish_reason':'length' if n>=settings['max_new_tokens'] else 'stop','generation':dict(settings,enable_thinking=True),'timings':timings,'submitted_image_count':image_count,'processed_image_count':actual_images,'video_frame_count':(payload.get('media') or {}).get('frame_count',0),'vlm_fps':float(os.environ['QWEN_VLM_FPS']),'cuda_synchronized':True,'ttft_ms':None}
  del generated,ids,inputs
  body['server_total_ms']=(time.perf_counter()-arrival)*1000
  return body
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def respond(self,status,body):
  raw=json.dumps(body).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
 def do_GET(self):self.respond(200,dict(manifest,status='ready'))
 def do_POST(self):
  try:
   payload=json.loads(self.rfile.read(int(self.headers['Content-Length'])));body=generate(payload)
   with open(Path(os.environ['QWEN_RUN'])/'server_calls.jsonl','a') as f:f.write(json.dumps(dict(context=payload.get('context'),**body))+'\n')
   self.respond(200,body)
  except Exception as exc:
   import traceback;traceback.print_exc();self.respond(500,{'error':type(exc).__name__,'message':str(exc)})
warm=generate({'messages':[{'role':'user','content':'Return exactly OK.'}],'purpose':'startup_warmup','max_new_tokens':256})
print('QWEN_SERVER_READY '+json.dumps(dict(manifest,warmup=warm)),flush=True)
ThreadingHTTPServer(('127.0.0.1',8766),Handler).serve_forever()
