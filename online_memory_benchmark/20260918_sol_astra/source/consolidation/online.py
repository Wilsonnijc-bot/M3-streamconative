"""Small opt-in M3 integration seam; existing construction code need not be rewritten."""
from copy import deepcopy
from .assignment_logger import LoggedVoiceGraph
from .common import digest, interval
from .replay import transcript_sources


def graph_fingerprint(graph):
    # Includes the sampled embedding pool that determines the next assignment.
    return 'online_'+digest({str(k):{'type':v.type,'metadata':v.metadata,
                                   'embeddings':v.embeddings} for k,v in graph.nodes.items()})


def assign_observation(graph, logger, ledger, audio, session_id, clip_id, index,
                       segment_start_s, audio_ref, assignment_run_id):
    """Replace one search/update block in process_voices. Returns the original M3 node ID.

    Invoke in the existing ordered graph writer. Scores are durably logged BEFORE
    add/update. The observation and resulting node ID are saved after mutation; on a
    crash between them the pre-mutation intent remains available for recovery.
    """
    from .common import seconds
    start=segment_start_s+seconds(audio['start_time'])
    end=segment_start_s+seconds(audio['end_time'])
    interval(start,end)
    if logger.session_id!=session_id or ledger.session_id!=session_id:
        raise ValueError('online session mismatch')
    uid=f'{session_id}/utt_{clip_id:04d}_{index:04d}'
    existing={o['utterance_id']:o for o in ledger.load()}
    if uid in existing:
        raise ValueError('observation already committed; do not mutate graph twice')
    before=graph_fingerprint(graph)
    transcripts=transcript_sources(audio['asr'])
    wrapper=LoggedVoiceGraph(graph,logger)
    wrapper.begin_observation(uid,end,before,transcripts)
    info={'embeddings':[audio['embedding']], 'contents':[audio['asr']]}
    matches=wrapper.search_voice_nodes(info)
    if matches:
        node_id=matches[0][0]
        graph.update_node(node_id,info)
    else:
        node_id=graph.add_voice_node(info)
    observation=dict(utterance_id=uid,session_id=session_id,clip_id=clip_id,start_time=start,end_time=end,
        original_voice_id='voice_'+str(node_id),transcripts=transcripts,original_transcript=audio['asr'],
        audio_ref=audio_ref,assignment_run_id=assignment_run_id,created_graph_version=graph_fingerprint(graph),
        original_assignment_evidence={'evidence_id':'assignment/'+uid,'graph_version_before_assignment':before,
            'scores_status':'recorded','assigned_voice_id':'voice_'+str(node_id)})
    ledger.append([observation])
    return node_id


class CommitScheduler:
    """Call after a successful graph commit; finalization is idempotent by cutoff."""
    def __init__(self,period_s=1200,last_run_cutoff=0,next_boundary=None):
        if period_s<=0:
            raise ValueError('period must be positive')
        self.period=period_s
        self.last_run=last_run_cutoff
        self.boundary=next_boundary or ((int(last_run_cutoff//period_s)+1)*period_s)
    def committed(self,cutoff_s,final=False):
        if cutoff_s<self.last_run:
            raise ValueError('committed cutoff moved backwards')
        if cutoff_s==self.last_run or (not final and cutoff_s<self.boundary):
            return False
        self.last_run=cutoff_s
        while self.boundary<=cutoff_s:
            self.boundary+=self.period
        return True
