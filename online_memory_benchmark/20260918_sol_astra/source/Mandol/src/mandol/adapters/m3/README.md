# M3 Mandol Adapter

This adapter consumes the embedding-free `m3-mandol/v1` directory exported by
StreamMeCo. It intentionally keeps the StreamMeCo and Mandol Python runtimes
separate.

## Commands

```bash
python -m mandol.adapters.m3 validate /path/to/interchange
python -m mandol.adapters.m3 build /path/to/interchange /path/to/mandol-graph
python -m mandol.adapters.m3 search /path/to/mandol-graph "what happened?" --scope clip:0
```

Set `API_302_KEY` (or `M3_MANDOL_302_API_KEY`) before build and
search. The default dense model is `Qwen/Qwen3-Embedding-0.6B` through
`https://api.302.ai/v1/embeddings`, with a required dimension of 1024.
The benchmark reranks with `qwen/qwen3-reranker-0.6b` through
`https://openrouter.ai/api/v1/rerank`. Optional relation extraction still uses
the Mandol `LLMClient` configuration `gemini-3.8-flash-302`.
Reranking requires a separate `OPENROUTER_API_KEY`.

## Mandol APIs Used

- `MemoryUnit`
- `SemanticMap` and `SemanticMap.load_map`
- `SemanticGraph` and `SemanticGraph.load_graph`
- `MemorySpaceRegistry.initialize_spaces`
- `SemanticGraph.batch_add_units`
- `SemanticGraph.add_relationship`
- `SemanticGraph.get_multi_retriever`
- `MultiRetriever.smart_search`
- `SemanticGraph.save_graph`

The adapter does not call `EntityRelationAutoBuilder.run_full_pipeline()`.
M3 person identifiers are already canonical and relation units require exact
evidence links that the generic auto-builder does not preserve.
