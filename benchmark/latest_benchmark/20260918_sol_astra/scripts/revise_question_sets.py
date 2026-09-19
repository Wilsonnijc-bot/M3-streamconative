"""User-corrected 102-question Jake Day1 and timeline-stratified 1000-question AEA."""
import csv,json
from bench_common import ROOT,read,atomic,sha
from build_question_manifests import clock_seconds

if __name__=='__main__':
    source=ROOT/'assets/questions/egolifeqa_benchmark.csv';revision=read(ROOT/'assets/questions/upstream_revision.json')
    questions=[]
    for r in csv.DictReader(source.open()):
        if not r['query_time_raw'].startswith('DAY1@'):continue
        choices=json.loads(r['choices']);answer=int(r['answer_index'])
        assert choices[answer]==r['answer_text']
        questions.append(dict(dataset='jake',question_id=r['question_id'],question=r['question'],ground_truth=chr(65+answer),
            options={chr(65+i):v for i,v in enumerate(choices)},query_timestamp=clock_seconds(r['query_time_raw'].split('@')[1]),
            source_annotation=dict(**revision,question_id=r['question_id'],query_time_raw=r['query_time_raw'],
                evidence_time_raw=json.loads(r['evidence_time_raw']),source_ids=json.loads(r['source_ids']),sha256=sha(source))))
    assert len(questions)==102
    questions.sort(key=lambda q:(q['query_timestamp'],int(q['question_id'].rsplit('-',1)[1])))
    atomic(ROOT/'configs/jake_questions.json',dict(dataset='jake',timestamp_basis='DAY1 source wall clock in seconds since midnight',questions=questions))
    original=ROOT/'assets/questions/aea_all_questions.json'
    if not original.exists():atomic(original,read(ROOT/'configs/aea_questions.json'))
    full=read(original);ordered=sorted(full['questions'],key=lambda q:(q['query_timestamp'],q['question_id']))
    n=1000;assert len(ordered)>=n
    indices=[(i*(len(ordered)-1))//(n-1) for i in range(n)]
    assert len(set(indices))==n
    selected=[ordered[i] for i in indices]
    atomic(ROOT/'configs/aea_questions.json',dict(dataset='aea',timestamp_basis=full['timestamp_basis'],
        selection=dict(rule='1000 evenly spaced ranks in timestamp/question-ID order, including first and last; no answer-based filtering',
            source_count=len(ordered),source_sha256=sha(original),selected_indices=indices),questions=selected))
    print('QUESTIONS jake=102 aea=1000')
