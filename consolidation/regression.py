"""Reproducible real-artifact contract regression, NOT a live model-quality evaluation."""
import argparse
import shutil
from pathlib import Path
from .common import read,write
from .replay import load_replay
from .pipeline import prepare,publish
from .llm_consolidator import propose


def run_case(replay,output,case,decisions,state_override=None):
    state,packet=prepare(replay,output)
    if state_override:
        state_override(state)
        from .evidence_builder import build_evidence
        packet=build_evidence(replay,state)
    work=Path(output)/'metadata'/case
    work.mkdir(parents=True,exist_ok=True)
    patch=dict(schema_version=1,session_id=replay['session_id'],base_graph_version=state['graph_version'],
               evidence_cutoff_s=packet['current_cutoff'],decisions=decisions)
    write(work/'recorded_patch.json',patch)
    patch=propose(packet,work,'test-fixture-not-an-LLM',patch_file=work/'recorded_patch.json')
    destination,report=publish(replay,output,state,packet,patch,llm_artifacts=work)
    return dict(case=case,cutoff=packet['current_cutoff'],observations=len(packet['observations']),
        ambiguous_assignments=sum(o['original_voice_id'] is None for o in packet['observations']),
        memories=len(packet['memories']),accepted=len(report['accepted']),rejected=len(report['rejected']),
        version=destination.name,audit=str((destination/'audit.md').relative_to(output)),
        graph=str((destination/'graph.json').relative_to(output)),
        evidence=str((destination/'evidence.json').relative_to(output)))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',default='consolidation/runs/regression')
    args=parser.parse_args()
    output=Path(args.output)
    if (output/'report.json').exists():
        raise SystemExit('Regression output already exists; choose a fresh --output directory')
    def merge(did,voices,target,ev):
        return dict(decision_id=did,op='merge_voice',voice_ids=voices,target_entity_id=target,evidence_ids=ev)
    cases=[]
    r20=load_replay('egolife_m3_jake_day1','egolife_m3_jake_day1/gemini',1200)
    cases.append(run_case(r20,output,'egolife_20',[
        merge('d1',['voice_364'],'person_0',['semantic_372']),
        dict(decision_id='d2',op='set_name',entity_id='person_0',name='Jake',evidence_ids=['semantic_372']),
        dict(decision_id='d3',op='resolve_reference',memory_node_id=372,mention='<voice_364>',entity_id='person_0',evidence_ids=['semantic_372']),
        dict(decision_id='d4',op='defer',target_ids=['voice_0'],reason='Do not assume the facilitator is the camera wearer; insufficient evidence for a merge.')]))
    r40=load_replay('egolife_m3_jake_day1','egolife_m3_jake_day1/gemini',2400)
    assert all(m['memory_node_id']!='740' for m in r20['memories'])
    cases.append(run_case(r40,output,'egolife_40',[
        merge('d1',['voice_311','voice_732'],'person_1',['semantic_740']),
        merge('d2',['voice_643'],'person_2',['semantic_654']),
        dict(decision_id='d3',op='set_name',entity_id='person_2',name='Tasha',evidence_ids=['semantic_654']),
        dict(decision_id='d4',op='resolve_reference',memory_node_id=654,mention='<voice_643>',entity_id='person_2',evidence_ids=['semantic_654']),
        dict(decision_id='d5',op='set_name',entity_id='person_1',name='Katrina',evidence_ids=['semantic_740'])]))
    m3=load_replay('m3bench_bedroom_01','m3bench_bedroom_01/gemini',2400,
                  'm3bench_bedroom_01/provenance/raw/gemini/results/memory/q11_uncompressed/metadata.json')
    cases.append(run_case(m3,output,'m3bench',[
        merge('d1',['voice_10','voice_310'],'person_0',['semantic_356']),
        merge('d2',['voice_10','voice_321','voice_322'],'person_0',['semantic_357']),
        dict(decision_id='d3',op='defer',target_ids=['voice_321','voice_322'],reason='Conflicting position claims; observation-level acoustic review required.')],
        state_override=lambda s:s['cannot_link'].append(['voice_10','voice_321'])))
    assert [(c['accepted'],c['rejected']) for c in cases]==[(4,0),(4,1),(2,1)]
    write(output/'report.json',dict(mode='recorded-patch contract regression',cases=cases,
        caveats=['No live LLM or MOSS inference in this regression.',
                 'M3Bench cannot_link is a test constraint, not a discovered ground-truth label.',
                 'Hash embeddings test publication consistency, not semantic retrieval quality.',
                 'No independent identity gold; identity accuracy metrics are not claimed.']))
    lines=['# Consolidation regression results','','These are **recorded test patches**, not live LLM discoveries.',
           'Original graph nodes, transcripts and historical assignment evidence are preserved.','',
           '| Case | Cutoff | Observations | Accepted / rejected | Outputs |',
           '| --- | ---: | ---: | ---: | --- |']
    for c in cases:
        lines.append(f"| {c['case']} | {c['cutoff']} s | {c['observations']} | {c['accepted']} / {c['rejected']} | [Audit]({c['audit']}) · [Graph]({c['graph']}) · [Evidence]({c['evidence']}) |")
    lines+=['','The 40-minute run carries the 20-minute registry forward. Its unsupported Katrina name is rejected.',
            'The M3-Bench test rejects a prohibited transitive merge. Its cannot-link constraint is injected for testing.',
            'MOSS and independent identity labels are not available in these test runs. Live quality comparisons remain unmeasured.','']
    (output/'README.md').write_text('\n'.join(lines))
    print('\n'.join(lines))


if __name__=='__main__':
    main()
