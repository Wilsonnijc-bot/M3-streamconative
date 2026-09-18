"""Version-local dense/lexical retrieval; never reuses stale source embeddings."""
import hashlib
import math
import re
from collections import Counter, defaultdict
import numpy as np
from .common import digest


def tokens(text):
    return re.findall(r'[a-z0-9_]+|[\u3400-\u9fff]',text.casefold())


class HashEmbedder:
    """Deterministic local smoke baseline, NOT a semantic embedding model."""
    model_id='signed-token-hash-v1-384'
    def encode(self,texts):
        vectors=[]
        for text in texts:
            vector=[0.0]*384
            for token in tokens(text):
                value=hashlib.sha256(token.encode()).digest()
                vector[int.from_bytes(value[:4],'big')%384] += 1 if value[4]&1 else -1
            norm=math.sqrt(sum(v*v for v in vector)) or 1
            vectors.append([v/norm for v in vector])
        return vectors


class SentenceTransformerEmbedder:
    def __init__(self, model_id):
        from sentence_transformers import SentenceTransformer
        self.model_id=model_id
        self.model=SentenceTransformer(model_id)
    def encode(self,texts):
        return self.model.encode(texts,normalize_embeddings=True).tolist()


def refresh(memories, state, embedder):
    active=[m for m in memories if m['retrieval_active']]
    texts=[m['canonical_text'] for m in active]
    vectors=embedder.encode(texts) if texts else []
    if len(vectors)!=len(texts):
        raise ValueError('embedding count mismatch')
    if vectors:
        values=np.asarray(vectors,dtype=float)
        if values.ndim!=2 or values.shape[1]==0 or not np.isfinite(values).all():
            raise ValueError('invalid dense embeddings')
    postings=defaultdict(dict)
    for m,text in zip(active,texts):
        for token,count in Counter(tokens(text)).items():
            postings[token][m['memory_node_id']]=count
    return dict(model_id=embedder.model_id, document_ids=[m['memory_node_id'] for m in active],
        text_digest=digest(texts), dense_vectors=vectors, lexical_postings=dict(postings),
        entity_mappings={m['memory_node_id']:m['entity_ids'] for m in active},
        mandol_entity_references={m['memory_node_id']:[{'session_id':state['session_id'],'entity_id':e}
            for e in m['entity_ids']] for m in active})


def search(index, query, embedder, limit=5):
    if index['model_id']!=embedder.model_id:
        raise ValueError('query embedding model mismatch')
    vector=embedder.encode([query])[0]
    scores={mid:sum(a*b for a,b in zip(vector,v)) for mid,v in zip(index['document_ids'],index['dense_vectors'])}
    for token in tokens(query):
        for mid,count in index['lexical_postings'].get(token,{}).items():
            scores[mid]+=math.log1p(count)
    return sorted(scores.items(),key=lambda p:(-p[1],p[0]))[:limit]


class APIEmbedder:
    """Configured embeddings endpoint; batch results ordered by response index."""
    def __init__(self,endpoint,model_id,key_env='CONSOLIDATION_API_KEY',batch_size=64):
        self.endpoint,self.model_id,self.key_env,self.batch_size=endpoint,model_id,key_env,batch_size
    def encode(self,texts):
        import json
        import os
        import urllib.request
        from .common import dumps
        vectors=[]
        for start in range(0,len(texts),self.batch_size):
            batch=texts[start:start+self.batch_size]
            headers={'Content-Type':'application/json'}
            if os.environ.get(self.key_env):
                headers['Authorization']='Bearer '+os.environ[self.key_env]
            request=urllib.request.Request(self.endpoint.rstrip('/')+'/embeddings',headers=headers,
                data=dumps({'model':self.model_id,'input':batch}).encode())
            with urllib.request.urlopen(request,timeout=180) as response:
                payload=json.load(response)
            rows=sorted(payload['data'],key=lambda d:d['index'])
            if [r['index'] for r in rows]!=list(range(len(batch))):
                raise ValueError('embedding API returned missing/duplicate indices')
            vectors.extend(r['embedding'] for r in rows)
        return vectors
