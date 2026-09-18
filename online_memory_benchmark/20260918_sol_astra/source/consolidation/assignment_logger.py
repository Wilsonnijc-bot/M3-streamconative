"""Logging wrapper around M3 voice search; capture every score before mutation."""
import fcntl
import json
import math
from pathlib import Path
import numpy as np
from .common import digest, dumps


def cam_candidates(graph, audio_info):
    query=np.asarray(audio_info['embeddings'],dtype=float)
    query=query.reshape(-1,query.shape[-1])
    query=query/np.maximum(np.linalg.norm(query,axis=1,keepdims=True),1e-30)
    result=[]
    for nid,node in graph.nodes.items():
        if node.type!='voice':
            continue
        vectors=np.asarray(node.embeddings,dtype=float).reshape(-1,query.shape[-1])
        vectors=vectors/np.maximum(np.linalg.norm(vectors,axis=1,keepdims=True),1e-30)
        score=float(np.mean(query@vectors.T))
        result.append(dict(candidate_id='voice_'+str(nid),score=score,
            eligible=score>=graph.audio_matching_threshold,
            rejection_reason=None if score>=graph.audio_matching_threshold else 'below_threshold'))
    return result


class AssignmentLogger:
    def __init__(self,path,session_id,model_version,config=None,gallery=None):
        self.path=Path(path)
        self.session_id=session_id
        self.model_version=model_version
        self.config=config or {}
        self.gallery=gallery
        self.gallery_digest=digest(gallery) if gallery is not None else None

    def record(self,utterance_id,available_at,graph_version,candidates,selected,threshold,
               method='CAM++',transcripts=None,intermediate=None):
        if method not in ('CAM++','TST'):
            raise ValueError('unsupported assignment method')
        if len({c['candidate_id'] for c in candidates})!=len(candidates):
            raise ValueError('duplicate assignment candidate')
        if any(not math.isfinite(c['score']) for c in candidates):
            raise ValueError('nonfinite assignment score')
        if method=='TST':
            if self.gallery is None or digest(self.gallery)!=self.gallery_digest:
                raise ValueError('fixed enrollment gallery required')
            if {c['candidate_id'] for c in candidates}!=set(self.gallery):
                raise ValueError('TST must log the complete enrollment gallery')
            if selected=='non_target':
                selected=None
        ids={c['candidate_id'] for c in candidates if c['eligible']}
        if selected is not None and selected not in ids:
            raise ValueError('selected candidate is not eligible')
        event=dict(evidence_id='assignment/'+utterance_id,kind='historical_assignment',
            session_id=self.session_id,utterance_id=utterance_id,available_at=available_at,
            graph_version_before_assignment=graph_version,method=method,model_version=self.model_version,
            config=self.config,gallery_digest=self.gallery_digest,candidates=candidates,
            selected_candidate=selected,threshold=threshold,
            decision='match' if selected else 'non_target' if method=='TST' else 'new_voice',
            reason='no_existing_candidates' if not candidates else None,
            transcripts=transcripts or {},intermediate=intermediate,
            score_origin='historical_pre_mutation')
        self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.path.open('a+') as handle:
            fcntl.flock(handle,fcntl.LOCK_EX)
            handle.seek(0)
            prior=[json.loads(line) for line in handle]
            if any(e['session_id']!=self.session_id for e in prior):
                raise ValueError('assignment log session mismatch')
            if method=='TST' and any(e.get('method')=='TST' and e.get('gallery_digest')!=self.gallery_digest for e in prior):
                raise ValueError('TST enrollment gallery changed across runs')
            same=[e for e in prior if e['evidence_id']==event['evidence_id']]
            if same:
                if same[0]!=event:
                    raise ValueError('immutable assignment evidence changed')
                return event
            handle.seek(0,2)
            handle.write(dumps(event)+'\n')
            handle.flush()
            import os
            os.fsync(handle.fileno())
        return event


class LoggedVoiceGraph:
    """Duck-typed wrapper; call begin_observation before each search/update pair."""
    def __init__(self,graph,logger):
        self.graph,self.logger=graph,logger
        self.context=None
    def __getattr__(self,name):
        return getattr(self.graph,name)
    def begin_observation(self,utterance_id,available_at,graph_version,transcripts):
        self.context=(utterance_id,available_at,graph_version,transcripts)
    def search_voice_nodes(self,audio_info):
        if self.context is None:
            raise ValueError('begin_observation must precede assignment')
        matches=self.graph.search_voice_nodes(audio_info)
        candidates=cam_candidates(self.graph,audio_info)
        uid,at,version,transcripts=self.context
        self.logger.record(uid,at,version,candidates,
            'voice_'+str(matches[0][0]) if matches else None,
            self.graph.audio_matching_threshold,transcripts=transcripts)
        self.context=None
        return matches
