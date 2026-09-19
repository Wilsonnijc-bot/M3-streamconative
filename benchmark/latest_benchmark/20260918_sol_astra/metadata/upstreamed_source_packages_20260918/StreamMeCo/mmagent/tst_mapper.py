"""Online ECAPA/TST frontend using the unchanged native M3 voice identity policy.

No pre-enrollment, person labels, or frozen gallery. Each construction graph owns
its voice nodes and retained embeddings; C1 and TST graphs never share vectors.
"""
import base64
import hashlib
import io
import json
from pathlib import Path
import time
import wave

class TSTVoiceMapper:
    def __init__(self,root,config_path,encoder=None):
        from tst.encoder import SpeechBrainEncoder
        from tst.audio import AudioExtractor
        self.root=Path(root);self.config=json.loads(Path(config_path).read_text())
        cfg=self.config
        if cfg['enrollment_policy']!='online_native_m3' or cfg['pre_enrollment'] is not False:raise ValueError('TST must use online native enrollment')
        self.encoder=encoder or SpeechBrainEncoder(dict(revision=cfg['encoder']['revision'],device='cuda',offline=True),self.root/'tst_assets/ecapa_model')
        if self.encoder.fingerprint!=cfg['encoder_fingerprint']:raise ValueError('ECAPA fingerprint mismatch')
        self.extractor=AudioExtractor(self.encoder,self.encoder.fingerprint,self.root/'cache/ecapa_embeddings')

    def map(self,graph,segment,transcript):
        from sklearn.metrics.pairwise import cosine_similarity
        import numpy as np
        began=time.perf_counter();cfg=self.config
        if graph.audio_matching_threshold!=cfg['threshold'] or graph.max_audio_embeddings!=cfg['max_audio_embeddings']:raise ValueError('native speaker policy mismatch')
        previous=getattr(graph,'speaker_encoder_fingerprint',None)
        if previous not in (None,cfg['encoder_fingerprint']):raise ValueError('mixed speaker encoder spaces')
        voices=[n for n in graph.nodes.values() if n.type=='voice']
        if any(n.metadata.get('embedding_space')!='speechbrain_ecapa_192' for n in voices):raise ValueError('non-ECAPA vectors in TST graph')
        graph.speaker_encoder_fingerprint=cfg['encoder_fingerprint']
        data=base64.b64decode(segment);key=hashlib.sha256(data).hexdigest()
        path=self.root/'cache/tst_query_audio'/f'{key}.wav';path.parent.mkdir(parents=True,exist_ok=True)
        if not path.exists():path.write_bytes(data)
        with wave.open(io.BytesIO(data)) as wav:duration=wav.getnframes()/wav.getframerate()
        vectors,hit,embedding_ms=self.extractor.extract(dict(audio_path=str(path),start_s=0.,end_s=duration))
        info=dict(embeddings=vectors.tolist(),contents=[transcript])
        # Exactly the same matching, thresholding, updating and creation APIs as CAM++.
        matched=graph.search_voice_nodes(info)
        scores={f'voice_{n.id}':float(np.mean(cosine_similarity(vectors,np.asarray(n.embeddings)))) for n in voices}
        best=max(scores.values()) if scores else None
        if matched:
            node=matched[0][0];graph.update_node(node,info);created=False
        else:
            node=graph.add_voice_node(info);created=True
        graph.nodes[node].metadata.update(speaker_mapping='TST',embedding_space='speechbrain_ecapa_192',method_id=cfg['method_id'])
        return node,dict(method_id=cfg['method_id'],best_score=best,threshold=graph.audio_matching_threshold,
            predicted_identity=f'voice_{node}',created_new_identity=created,cache_hit=hit,embedding_ms=embedding_ms,
            mapping_total_ms=(time.perf_counter()-began)*1000,audio_sha256=key,candidate_scores=scores,
            query_window_count=len(vectors),retained_embeddings=len(graph.nodes[node].embeddings),enrollment_policy='online_native_m3')
