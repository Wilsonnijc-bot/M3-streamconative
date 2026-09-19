from pathlib import Path
p=Path('Mandol/benchmarks/egolife_m3_first10.py');s=p.read_text()
s=s.replace('from mandol.retrieval.query_bundle import QueryBundle','from mandol.retrieval.query_bundle import QueryBundle\nfrom mandol.retrieval.score_fusion import ScoreFusion')
s=s.replace('    prep_started = time.perf_counter()\n    candidate_uids','    total_started = time.perf_counter()\n    prep_started = time.perf_counter()\n    candidate_uids',1)
s=s.replace('    search_started = time.perf_counter()\n    try:', '''    stage_events = []
    original_fusion = ScoreFusion.rrf_fusion
    def timed_fusion(*a, **kw):
        t = time.perf_counter()
        try:
            return original_fusion(*a, **kw)
        finally:
            stage_events.append({'stage':'fusion', 'latency_ms':(time.perf_counter()-t)*1000})
    ScoreFusion.rrf_fusion = staticmethod(timed_fusion)
    original_get = retriever.graph.get_unit
    def timed_get(*a, **kw):
        t = time.perf_counter()
        try:
            return original_get(*a, **kw)
        finally:
            stage_events.append({'stage':'memory_unit_lookup', 'latency_ms':(time.perf_counter()-t)*1000})
    retriever.graph.get_unit = timed_get
    search_started = time.perf_counter()
    try:''',1)
s=s.replace('        restore_retrievers(multi, originals)','        restore_retrievers(multi, originals)\n        ScoreFusion.rrf_fusion = staticmethod(original_fusion)\n        retriever.graph.get_unit = original_get',1)
s=s.replace('    ranked = detailed.get("results", []) if isinstance(detailed, dict) else detailed','    if isinstance(detailed, dict) and detailed.get("error"):\n        raise RuntimeError(detailed["error"])\n    if {e["method"] for e in backend_events} != {"bm25", "cosine_similarity", "splade"}:\n        raise RuntimeError("Mandol did not execute all three hybrid backends")\n    ranked = detailed.get("results", []) if isinstance(detailed, dict) else detailed',1)
s=s.replace('    total_ms = query_preparation_ms + mandol_search_ms + rerank_metrics["latency_ms"]','    total_ms = (time.perf_counter()-total_started)*1000\n    fusion_ms = sum(e["latency_ms"] for e in stage_events if e["stage"]=="fusion")\n    lookup_ms = sum(e["latency_ms"] for e in stage_events if e["stage"]=="memory_unit_lookup")',1)
s=s.replace('"Mandol_search_ms": mandol_search_ms,','"Mandol_search_ms": mandol_search_ms,\n            "fusion_ms": fusion_ms,\n            "memory_unit_lookup_ms": lookup_ms,\n            "memory_space_selection_ms": query_preparation_ms,\n            "stage_events": stage_events,\n            "timing_note": "Backend timings include nested embedding and unit lookup; stages overlap and must not be summed.",',1)
s=s.replace('            "uid": unit.uid,','            "uid": unit.uid,\n            "memory_spaces": sorted(getattr(unit, "space_ids", []) or []),',1)
s=s.replace('                "provenance": item["provenance"],','                "provenance": item["provenance"],\n                "memory_spaces": item["memory_spaces"],',1)
p.write_text(s)
