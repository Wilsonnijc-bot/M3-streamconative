"""Isolated Mandol runtime: build, reload, verify, then acknowledge readiness."""
import argparse
import json
from pathlib import Path

from .common import read, write


def main():
    parser = argparse.ArgumentParser()
    for name in ('input','output','config','version','receipt'):
        parser.add_argument('--'+name, required=True)
    args = parser.parse_args()
    from mandol.adapters.m3.adapter import M3MandolAdapter, M3MandolConfig
    from mandol.adapters.m3.retriever import M3MandolRetriever
    from mandol.adapters.m3.uids import memory_uid
    from mandol.retrieval.retrieval_interface import RetrievalMethod
    settings = read(args.config)['mandol']
    from mandol.utils.model_manager import global_model_manager
    if settings.get('generate_sparse_embeddings', True):
        if global_model_manager.get_splade_model() is None:
            raise RuntimeError('configured SPLADE checkpoint unavailable; check MANDOL_WORKDIR/model installation')
    result = M3MandolAdapter.build(args.input, args.output, M3MandolConfig(**settings))
    result['source_graph_version'] = args.version
    write(Path(args.output)/'m3_adapter_manifest.json', result)
    retriever = M3MandolRetriever.load(args.output)
    records = [json.loads(line) for line in (Path(args.input)/'memories.jsonl').read_text(encoding='utf-8').splitlines()]
    for record in records:
        uid = memory_uid(result['video_id'], record['clip_id'], record['memory_type'], record['m3_node_id'])
        unit = retriever.graph.get_unit(uid)
        if unit is None or unit.raw_data['text_content'] != record['text']:
            raise ValueError('reloaded Mandol memory differs from canonical export: '+uid)
        if unit.embedding is None or len(unit.embedding) != settings['embedding_dimension']:
            raise ValueError('reloaded Mandol dense embedding is missing: '+uid)
        if settings.get('generate_sparse_embeddings', True) and unit.sparse_embedding is None:
            raise ValueError('reloaded Mandol sparse embedding is missing: '+uid)
    indexes = retriever.graph.get_multi_retriever()
    for method in (RetrievalMethod.BM25, RetrievalMethod.SPLADE):
        indexes._ensure_retriever_loaded(method)
        if not getattr(indexes.retrievers[method], '_index_built', False):
            raise ValueError('persisted Mandol index did not load: '+str(method))
    probe = []
    if records:
        probe = retriever.search(records[0]['text'][:500], top_k=3)
        if not probe:
            raise ValueError('reloaded Mandol hybrid retrieval returned no results')
    write(args.receipt, dict(status='ready', graph_version=args.version,
        memory_count=len(records), embedding=result['mandol_embedding'],
        dense_verified=True, bm25_verified=True, splade_verified=True,
        hybrid_probe_results=len(probe)))
    print('MANDOL_REINDEX_READY', args.version, len(records), flush=True)


if __name__ == '__main__':
    main()
