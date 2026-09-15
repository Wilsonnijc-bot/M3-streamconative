#!/usr/bin/env python3
"""Build and evaluate Mandol graphs adapted from ten M3 query-time snapshots."""

from __future__ import annotations

import argparse
import json
import os
import re
import threading
import time
from pathlib import Path

import sys
sys.path.insert(0, os.environ.get("STREAMMECO_ROOT", "/opt/streammeco/run/StreamMeCo"))
from benchmarks import qwen_runtime as runtime
import httpx
import cloud_http
from openai import OpenAI

from mandol.adapters.m3.adapter import M3MandolAdapter, M3MandolConfig
from mandol.adapters.m3.embedding import OpenAICompatible302EmbeddingAdapter
from mandol.adapters.m3.retriever import M3MandolRetriever
from mandol.retrieval.query_bundle import QueryBundle
from mandol.retrieval.score_fusion import ScoreFusion
from mandol.retrieval.retrieval_interface import RetrievalMethod

LETTERS = ["A", "B", "C", "D"]
OUTPUT_NAMES = {"qwen": "method_D_mandol.jsonl"}
EMBEDDING_MODEL = "Qwen/Qwen3-Embedding-0.6B"
RERANK_MODEL = "Qwen/Qwen3-Reranker-0.6B"
_embedding_events: list[dict] | None = None
_embedding_lock = threading.Lock()


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["adapt", "eval"])
    parser.add_argument("--qa", type=Path, required=True)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--backend", choices=["qwen"], default="qwen")
    parser.add_argument("--qwen-url", default="http://127.0.0.1:8765/generate")
    parser.add_argument("--top-k", type=int, default=2)
    parser.add_argument("--candidate-k", type=int, default=20)
    parser.add_argument("--limit", type=int, default=10)
    return parser.parse_args()


def write_json(value, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def append_jsonl(value, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(value, ensure_ascii=False) + "\n")
        handle.flush()


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def clock_seconds(value) -> float:
    value = str(value).zfill(8)
    return int(value[:2]) * 3600 + int(value[2:4]) * 60 + int(value[4:6]) + int(value[6:]) / 100


def load_questions(path: Path) -> tuple[list[dict], list[dict]]:
    rows = json.loads(path.read_text())
    rows = [row for row in rows if row.get("query_time", {}).get("date") == "DAY1"]
    rows.sort(key=lambda row: clock_seconds(row["query_time"]["time"]))
    selected = rows[:10]
    public = [
        {
            "id": str(row["ID"]),
            "query_time": row["query_time"],
            "question": row["question"],
            "choices": {
                letter: row[key]
                for letter, key in zip(
                    LETTERS, ["choice_a", "choice_b", "choice_c", "choice_d"]
                )
            },
        }
        for row in selected
    ]
    return selected, public


def question_text(question: dict) -> str:
    choices = "\n".join(f"{letter}. {question['choices'][letter]}" for letter in LETTERS)
    return f"{question['question']}\n{choices}"


def direct_302_client() -> OpenAI:
    api_key = os.environ.get("API_302_KEY") or os.environ.get("M3_MANDOL_302_API_KEY")
    if not api_key:
        raise ValueError("API_302_KEY is missing")
    direct_ip = os.environ.get("API_302_DIRECT_IP", "20.255.184.187")
    transport = httpx.Client(
        verify=False,
        trust_env=False,
        headers={"Host": "api.302.ai"},
        timeout=120,
    )
    return OpenAI(
        api_key=api_key,
        base_url=f"https://{direct_ip}/v1",
        http_client=transport,
        max_retries=0,
    )


def install_embedding_trace():
    original = OpenAICompatible302EmbeddingAdapter._embed_batch

    def traced(self, texts):
        started = time.perf_counter()
        vectors = original(self, texts)
        event = {
            "input_count": len(texts),
            "input_chars": sum(len(text) for text in texts),
            "latency_ms": (time.perf_counter() - started) * 1000,
            "provider": "302.ai",
            "model": EMBEDDING_MODEL,
        }
        with _embedding_lock:
            if _embedding_events is not None:
                _embedding_events.append(event)
        return vectors

    OpenAICompatible302EmbeddingAdapter._embed_batch = traced
    return original


def restore_embedding_trace(original):
    OpenAICompatible302EmbeddingAdapter._embed_batch = original


def adapt(args, questions: list[dict]):
    global _embedding_events
    client = direct_302_client()
    original = install_embedding_trace()
    try:
        for index, _question in enumerate(questions, 1):
            root = args.results / "mandol_adapted" / f"q{index:02d}"
            graph_dir = root / "graph"
            metrics_path = root / "adapter_metrics.json"
            if (graph_dir / "m3_adapter_manifest.json").exists() and metrics_path.exists():
                continue
            export_metrics = json.loads((root / "export_metrics.json").read_text())
            _embedding_events = []
            started = time.perf_counter()
            result = M3MandolAdapter.build(
                root / "interchange",
                graph_dir,
                M3MandolConfig(
                    embedding_model=EMBEDDING_MODEL,
                    embedding_dimension=1024,
                    embedding_base_url="https://api.302.ai/v1",
                    embedding_batch_size=32,
                    build_relations=False,
                    generate_sparse_embeddings=True,
                    overwrite=True,
                    embedding_client=client,
                ),
            )
            build_ms = (time.perf_counter() - started) * 1000
            embedding_events = list(_embedding_events)
            _embedding_events = None
            metrics = {
                "export_ms": export_metrics["export_ms"],
                "mandol_build_ms": build_ms,
                "adaptor_ms": export_metrics["export_ms"] + build_ms,
                "embedding": {
                    "call_count": len(embedding_events),
                    "each_call_ms": [row["latency_ms"] for row in embedding_events],
                    "total_ms": sum(row["latency_ms"] for row in embedding_events),
                    "provider": "302.ai",
                    "model": EMBEDDING_MODEL,
                    "calls": embedding_events,
                    "source_m3_vectors_imported": False,
                },
                "relations": {
                    "generated_relations_enabled": False,
                    "reason": "Preserve native M3-derived memory without adding LLM-generated facts",
                },
                "result": result,
            }
            write_json(metrics, metrics_path)
            append_jsonl(
                {
                    "question_index": index,
                    "method": "D",
                    "model": None,
                    "event": "adaptor",
                    **metrics,
                },
                args.results / "detailed_latency_events.jsonl",
            )
            print(f"MANDOL_ADAPT_COMPLETE q={index:02d}", flush=True)
    finally:
        restore_embedding_trace(original)


def wrap_retrievers(multi):
    events: list[dict] = []
    lock = threading.Lock()
    originals = {}
    for method in (
        RetrievalMethod.BM25,
        RetrievalMethod.COSINE_SIMILARITY,
        RetrievalMethod.SPLADE,
    ):
        if not multi._ensure_retriever_loaded(method):
            raise RuntimeError(f"Mandol could not load required backend {method.value}")
        backend = multi.retrievers[method]
        originals[method] = backend.search

        def wrapped(*args, _method=method, _original=backend.search, **kwargs):
            started = time.perf_counter()
            result = _original(*args, **kwargs)
            with lock:
                events.append(
                    {
                        "method": _method.value,
                        "latency_ms": (time.perf_counter() - started) * 1000,
                        "result_count": len(result),
                    }
                )
            return result

        backend.search = wrapped
    return events, originals


def restore_retrievers(multi, originals):
    for method, original in originals.items():
        multi.retrievers[method].search = original


def rerank_302(query: str, candidates: list[dict], top_k: int) -> tuple[list[dict], dict]:
    if not candidates:
        return [], {
            "latency_ms": 0.0,
            "model": RERANK_MODEL,
            "provider": "302.ai",
            "candidate_count": 0,
        }
    api_key = os.environ.get("API_302_KEY") or os.environ.get("M3_MANDOL_302_API_KEY")
    direct_ip = os.environ.get("API_302_DIRECT_IP", "20.255.184.187")
    payload = {
        "model": RERANK_MODEL,
        "query": query,
        "documents": [item["text"] for item in candidates],
        "top_n": min(top_k, len(candidates)),
        "return_documents": False,
    }
    started = time.perf_counter()
    response = cloud_http.post(
        f"https://{direct_ip}/v1/rerank",
        direct=True, timeout=300,
        headers={
            "Host": "api.302.ai",
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
    )
    latency_ms = (time.perf_counter() - started) * 1000
    response.raise_for_status()
    body = response.json()
    ranked = []
    for row in body.get("results", []):
        candidate = dict(candidates[int(row["index"])])
        candidate["pre_rerank_score"] = candidate["score"]
        candidate["score"] = float(row.get("relevance_score", row.get("score", 0.0)))
        ranked.append(candidate)
    metrics = {
        "latency_ms": latency_ms,
        "api_request_wall_clock_latency_ms": latency_ms,
        "model": RERANK_MODEL,
        "provider": "302.ai",
        "candidate_count": len(candidates),
        "returned_count": len(ranked),
        "usage": body.get("usage"),
    }
    return ranked[:top_k], metrics


def mandol_search(retriever: M3MandolRetriever, query: str, top_k: int, candidate_k: int):
    global _embedding_events
    total_started = time.perf_counter()
    prep_started = time.perf_counter()
    candidate_uids = sorted(retriever._candidate_uids(None))
    query_bundle = QueryBundle(query)
    query_preparation_ms = (time.perf_counter() - prep_started) * 1000
    existing = getattr(retriever.graph,"_multi_retriever",None)
    warm_engine = existing is not None and all(m in existing.retrievers for m in (RetrievalMethod.BM25,RetrievalMethod.COSINE_SIMILARITY,RetrievalMethod.SPLADE))
    initialization_started = time.perf_counter()
    multi = retriever.graph.get_multi_retriever()
    backend_events, originals = wrap_retrievers(multi)
    initialization_ms = (time.perf_counter()-initialization_started)*1000
    _embedding_events = []
    stage_events = []
    original_fusion = ScoreFusion.rrf_fusion
    def timed_fusion(*a, **kw):
        t = time.perf_counter()
        try:
            return original_fusion(*a, **kw)
        finally:
            stage_events.append({'stage':'fusion', 'latency_ms':(time.perf_counter()-t)*1000})
    ScoreFusion.rrf_fusion = staticmethod(timed_fusion)
    original_get = retriever.graph.semantic_map.get_unit
    def timed_get(*a, **kw):
        t = time.perf_counter()
        try:
            return original_get(*a, **kw)
        finally:
            stage_events.append({'stage':'memory_unit_lookup', 'latency_ms':(time.perf_counter()-t)*1000})
    retriever.graph.semantic_map.get_unit = timed_get
    original_dense = retriever.graph.semantic_map.search_similarity_by_vector
    def timed_dense(*a, **kw):
        t = time.perf_counter()
        try:
            return original_dense(*a, **kw)
        finally:
            stage_events.append({'stage':'dense_vector_search', 'latency_ms':(time.perf_counter()-t)*1000})
    retriever.graph.semantic_map.search_similarity_by_vector = timed_dense
    search_started = time.perf_counter()
    try:
        detailed = multi.smart_search(
            query_bundle,
            methods=[
                RetrievalMethod.BM25,
                RetrievalMethod.COSINE_SIMILARITY,
                RetrievalMethod.SPLADE,
            ],
            top_k=max(candidate_k, top_k),
            fusion_method="rrf",
            rerank_method=None,
            enable_graph_expansion=False,
            candidate_uids=candidate_uids,
            return_detailed=True,
        )
    finally:
        mandol_search_ms = (time.perf_counter() - search_started) * 1000
        restore_retrievers(multi, originals)
        ScoreFusion.rrf_fusion = staticmethod(original_fusion)
        retriever.graph.semantic_map.get_unit = original_get
        retriever.graph.semantic_map.search_similarity_by_vector = original_dense
    embedding_events = list(_embedding_events)
    _embedding_events = None
    if isinstance(detailed, dict) and detailed.get("error"):
        raise RuntimeError(detailed["error"])
    if {e["method"] for e in backend_events} != {"bm25", "cosine_similarity", "splade"}:
        raise RuntimeError("Mandol did not execute all three hybrid backends")
    ranked = detailed.get("results", []) if isinstance(detailed, dict) else detailed
    lookup_started = time.perf_counter()
    candidates = [
        {
            "uid": unit.uid,
            "memory_spaces": sorted(name for name, space in retriever.graph.semantic_map.memory_spaces.items() if space.contains_unit(unit.uid, recursive=False)),
            "score": float(score),
            "text": unit.raw_data.get("text_content", unit.text_cached),
            "metadata": unit.metadata,
            "provenance": unit.metadata.get("provenance"),
        }
        for unit, score in ranked[:candidate_k]
    ]
    candidate_lookup_ms = (time.perf_counter()-lookup_started)*1000
    reranked, rerank_metrics = rerank_302(query, candidates, top_k)
    by_method = {
        method: sum(row["latency_ms"] for row in backend_events if row["method"] == method)
        for method in ("bm25", "cosine_similarity", "splade")
    }
    embedding = {
        "call_count": len(embedding_events),
        "each_call_ms": [row["latency_ms"] for row in embedding_events],
        "total_ms": sum(row["latency_ms"] for row in embedding_events),
        "provider": "302.ai",
        "model": EMBEDDING_MODEL,
        "calls": embedding_events,
    }
    total_ms = (time.perf_counter()-total_started)*1000
    fusion_ms = sum(e["latency_ms"] for e in stage_events if e["stage"]=="fusion")
    lookup_ms = sum(e["latency_ms"] for e in stage_events if e["stage"]=="memory_unit_lookup")
    metrics = {
        "query_text": query,
        "query_preparation_ms": query_preparation_ms,
        "embedding": embedding,
        "retrieval": {
            "dense_ms": sum(e["latency_ms"] for e in stage_events if e["stage"]=="dense_vector_search"),
            "dense_backend_inclusive_ms": by_method["cosine_similarity"],
            "retriever_initialization_ms": 0.0 if warm_engine else initialization_ms,
            "retriever_readiness_check_ms": initialization_ms if warm_engine else 0.0,
            "warm_engine": warm_engine,
            "query_feature_metrics": query_bundle.get_stats(),
            "sparse_ms": by_method["bm25"] + by_method["splade"],
            "StreamMeCo/TMR_ms": 0.0,
            "Mandol_search_ms": mandol_search_ms,
            "fusion_ms": fusion_ms,
            "memory_unit_lookup_ms": lookup_ms,
            "candidate_space_lookup_ms": candidate_lookup_ms,
            "memory_space_selection_ms": query_preparation_ms,
            "stage_events": stage_events,
            "timing_note": "Backend timings include nested embedding and unit lookup; stages overlap and must not be summed.",
            "graph_traversal_ms": 0.0,
            "rerank_ms": rerank_metrics["latency_ms"],
            "other_ms": query_preparation_ms,
            "TOTAL_RETRIEVAL_MS": total_ms,
            "backend_calls": backend_events,
        },
        "rerank": rerank_metrics,
        "retrieval_round_total_ms": total_ms,
        "returned_node_ids": [item["uid"] for item in reranked],
        "returned_node_scores": {item["uid"]: item["score"] for item in reranked},
        "evidence": [
            {
                "rank": rank,
                "node_id": item["uid"],
                "m3_node_id": item["metadata"].get("m3_node_id"),
                "node_type": item["metadata"].get("memory_type"),
                "timestamp": item["metadata"].get("clip_id"),
                "score": item["score"],
                "contents": [item["text"]],
                "provenance": item["provenance"],
                "memory_spaces": item["memory_spaces"],
            }
            for rank, item in enumerate(reranked, 1)
        ],
    }
    return reranked, metrics


model_call = runtime.text_call


def parse_prediction(text: str) -> str:
    matches = re.findall(r"(?:^|\b)([ABCD])(?:\b|[.)])", text.upper())
    return matches[-1] if matches else ""


def evaluate(args, questions: list[dict], public_questions: list[dict]):
    if not args.backend:
        raise ValueError("eval requires --backend")
    output = args.results / OUTPUT_NAMES[args.backend]
    completed = {row["question_index"] for row in read_jsonl(output)} if output.exists() else set()
    from benchmarks.warm_query import prepare_warm_query
    client = direct_302_client()
    original = install_embedding_trace()
    try:
        for index, (qa, question) in enumerate(zip(questions, public_questions), 1):
            if index in completed:
                continue
            root = args.results / "mandol_adapted" / f"q{index:02d}"
            adapter_metrics = json.loads((root / "adapter_metrics.json").read_text())
            load_started=time.perf_counter()
            retriever = M3MandolRetriever.load(root / "graph", embedding_client=client)
            load_ms=(time.perf_counter()-load_started)*1000
            manifest = retriever.build_manifest
            assert manifest['source_embedding']['vectors_imported'] is False
            assert manifest['mandol_embedding']['model'] == EMBEDDING_MODEL
            assert manifest['mandol_embedding']['dimension'] == 1024
            assert manifest['counts']['relation_llm_calls'] == 0
            write_json({str(u.metadata['m3_node_id']):u.uid for u in retriever.graph.get_all_units() if 'm3_node_id' in u.metadata}, root / 'mapping_m3_to_mandol.json')
            warmup=prepare_warm_query(lambda probe: mandol_search(retriever,probe,args.top_k,args.candidate_k),
                                      args.results,"D",index,load_ms)
            runtime.CONTEXT.update(question_id=question["id"], method="D")
            started = time.perf_counter()
            query = question["question"]
            evidence, retrieval_metrics = mandol_search(
                retriever, query, args.top_k, args.candidate_k
            )
            prompt = (
                "Answer this multiple-choice question using only the retrieved memories. "
                "Return exactly one letter: A, B, C, or D.\n\n"
                f"Question:\n{question_text(question)}\n\nRetrieved memories:\n"
                + json.dumps(evidence, ensure_ascii=False)
            )
            call = model_call(args.backend, prompt, args.qwen_url)
            prediction = parse_prediction(call["response"])
            gold = qa["answer"]
            manifest = json.loads((root / "graph" / "m3_adapter_manifest.json").read_text())
            counts = manifest["counts"]
            result = {
                "question_index": index,
                "question": question,
                "method": "D",
                "latency_mode": "warm_retrieval_uncached_question",
                "snapshot_load_ms_excluded": load_ms,
                "warmup_ms_excluded": warmup["warmup_ms"],
                "model": args.backend,
                "memory": {
                    "nodes": counts["source_memories"]
                    + counts["entities"]
                    + counts["relations"],
                    "source_memories": counts["source_memories"],
                    "entities": counts["entities"],
                    "relations": counts["relations"],
                },
                "adaptor_ms": adapter_metrics["adaptor_ms"],
                "adaptor_embedding": adapter_metrics["embedding"],
                "retrieval_query": query,
                "top_k": args.top_k,
                "retrieval_round_count": 1,
                "retrieval_rounds": [retrieval_metrics],
                "controller": {"call_count": 0, "each_call_ms": [], "total_ms": 0.0},
                "controller_calls": [],
                "final_answer_call": call,
                "final_answer_model_ms": call["latency_ms"],
                "FULL_QUESTION_TO_ANSWER_MS": (time.perf_counter() - started) * 1000,
                "retrieved_evidence": retrieval_metrics["evidence"],
                "retrieved_node_ids": retrieval_metrics["returned_node_ids"],
                "prediction": prediction,
                "raw_answer": call["response"],
                "gold_answer": gold,
                "correct": prediction == gold,
            }
            append_jsonl(result, output)
            append_jsonl(
                {
                    "question_index": index,
                    "method": "D",
                    "model": args.backend,
                    "event": "retrieval",
                    "round": 1,
                    **retrieval_metrics,
                },
                args.results / "detailed_latency_events.jsonl",
            )
            append_jsonl(
                {
                    "question_index": index,
                    "method": "D",
                    "model": args.backend,
                    "event": "final_answer",
                    **call,
                },
                args.results / "detailed_latency_events.jsonl",
            )
            print(
                f"EVAL_COMPLETE method=D model={args.backend} q={index:02d} "
                f"prediction={prediction} correct={prediction == gold}",
                flush=True,
            )
    finally:
        restore_embedding_trace(original)


def main() -> int:
    args = parse_args()
    runtime.configure(args.results, args.phase)
    questions, public_questions = load_questions(args.qa)
    questions, public_questions = questions[:args.limit], public_questions[:args.limit]
    if args.phase == "adapt":
        adapt(args, questions)
    else:
        evaluate(args, questions, public_questions)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
