"""Command-line entry points for the M3 Mandol adapter."""

from __future__ import annotations

import argparse
import json

from .adapter import M3MandolAdapter, M3MandolConfig
from .embedding import DEFAULT_BASE_URL, DEFAULT_MODEL
from .retriever import M3MandolRetriever
from .schema import load_interchange


def _scope(value: str | None) -> str | dict[str, int] | None:
    if value is None:
        return None
    if ":" not in value:
        return value
    kind, raw_id = value.split(":", 1)
    if kind in {"clip", "block"}:
        return {kind: int(raw_id)}
    if kind == "video":
        return {kind: raw_id}
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m mandol.adapters.m3")
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser(
        "validate", help="Validate an M3 interchange directory"
    )
    validate.add_argument("input_dir")

    build = commands.add_parser("build", help="Build and persist a Mandol graph")
    build.add_argument("input_dir")
    build.add_argument("output_dir")
    build.add_argument("--embedding-model", default=DEFAULT_MODEL)
    build.add_argument("--embedding-dimension", type=int, default=1024)
    build.add_argument("--embedding-base-url", default=DEFAULT_BASE_URL)
    build.add_argument("--embedding-batch-size", type=int, default=32)
    build.add_argument("--relation-model", default="gemini-3.8-flash-302")
    build.add_argument("--relation-base-url", default="https://api.302.ai/v1")
    build.add_argument("--skip-relations", action="store_true")
    build.add_argument("--no-splade", action="store_true")
    build.add_argument("--overwrite", action="store_true")

    search = commands.add_parser("search", help="Search a persisted M3 Mandol graph")
    search.add_argument("graph_dir")
    search.add_argument("query")
    search.add_argument("--top-k", type=int, default=10)
    search.add_argument(
        "--scope", help="video:ID, block:N, clip:N, or an exact space name"
    )
    search.add_argument("--graph-expansion", action="store_true")
    search.add_argument("--rerank-method")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "validate":
        data = load_interchange(args.input_dir)
        result = {
            "valid": True,
            "schema_version": data.manifest.schema_version,
            "video_id": data.manifest.video_id,
            "memories": len(data.memories),
            "entities": len(data.entities),
        }
    elif args.command == "build":
        config = M3MandolConfig(
            embedding_model=args.embedding_model,
            embedding_dimension=args.embedding_dimension,
            embedding_base_url=args.embedding_base_url,
            embedding_batch_size=args.embedding_batch_size,
            relation_model=args.relation_model,
            relation_base_url=args.relation_base_url,
            build_relations=not args.skip_relations,
            generate_sparse_embeddings=not args.no_splade,
            overwrite=args.overwrite,
        )
        result = M3MandolAdapter.build(args.input_dir, args.output_dir, config)
    else:
        retriever = M3MandolRetriever.load(args.graph_dir)
        result = retriever.search(
            args.query,
            top_k=args.top_k,
            scope=_scope(args.scope),
            enable_graph_expansion=args.graph_expansion,
            rerank_method=args.rerank_method,
        )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0
