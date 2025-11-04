#!/usr/bin/env python
"""Bulk load clustered demo chunks into VectorDB via the SDK.

Usage:
    python scripts/load_dummy_chunks.py \
        --base-url http://localhost:8000 \
        --data-file data/chunk_clusters.jsonl \
        --library-name clustered-demo \
        --build-index
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

from vectordb_client import ClientConfig, VectorDBClient, models as M
from vectordb_client.exceptions import Conflict, NotFound, VectorDBError


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parent.parent
    default_data = root / "data" / "chunk_clusters.jsonl"

    parser = argparse.ArgumentParser(
        description="Bulk load clustered demo chunks into VectorDB."
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="VectorDB API base URL (default: %(default)s)",
    )
    parser.add_argument(
        "--data-file",
        default=str(default_data),
        help="Path to JSONL file containing chunk records (default: %(default)s)",
    )
    parser.add_argument(
        "--library-name",
        default="clustered-demo",
        help="Library name to create or reuse (default: %(default)s)",
    )
    parser.add_argument(
        "--library-description",
        default="Demo library seeded with clustered chunks",
        help="Description used when creating the library",
    )
    parser.add_argument(
        "--build-index",
        action="store_true",
        help="Build an RP index after loading data",
    )
    parser.add_argument(
        "--algo",
        default="rp",
        choices=["rp", "flat"],
        help="Index algorithm to build when --build-index is set (default: %(default)s)",
    )
    parser.add_argument(
        "--metric",
        default="cosine",
        choices=["cosine", "l2"],
        help="Similarity metric for index builds (default: %(default)s)",
    )
    parser.add_argument(
        "--trees",
        type=int,
        default=8,
        help="RP forest trees (default: %(default)s)",
    )
    parser.add_argument(
        "--leaf-size",
        type=int,
        default=64,
        help="RP forest leaf size (default: %(default)s)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Seed for RP forest build (default: %(default)s)",
    )
    return parser.parse_args()


def load_dataset(path: Path) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(f"Data file not found: {path}")

    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def ensure_library(cli: VectorDBClient, name: str, description: str) -> M.Library:
    existing = [lib for lib in cli.list_libraries() if lib.name == name]
    if existing:
        lib = existing[0]
        print(f"[info] Reusing existing library {lib.id} ({lib.name})")
        return lib

    lib = cli.create_library(name, description)
    print(f"[info] Created library {lib.id} ({lib.name})")
    return lib


def ensure_document(cli: VectorDBClient, lib_id: str, title: str) -> M.Document:
    # documents API scoped by library; there is no direct filter by title, so
    # we always create new to keep mapping predictable.
    return cli.create_document(lib_id, title)


def main() -> None:
    args = parse_args()
    data_file = Path(args.data_file)
    rows = load_dataset(data_file)
    if not rows:
        raise RuntimeError(f"No rows found in {data_file}")

    cfg = ClientConfig(base_url=args.base_url)
    cli = VectorDBClient(cfg)

    try:
        library = ensure_library(cli, args.library_name, args.library_description)
    except VectorDBError as exc:
        raise SystemExit(f"Failed to create or fetch library: {exc}") from exc

    cluster_docs: dict[int, str] = {}
    cluster_counts: defaultdict[int, int] = defaultdict(int)

    for row in rows:
        cluster_id = int(row.get("cluster_id", -1))
        doc_title = row.get("document_title") or f"Cluster {cluster_id}"
        metadata = row.get("metadata", {}) or {}
        metadata.setdefault("cluster", cluster_id)

        if cluster_id not in cluster_docs:
            doc = ensure_document(cli, library.id, doc_title)
            cluster_docs[cluster_id] = doc.id

        doc_id = cluster_docs[cluster_id]
        cli.create_chunk(
            library.id,
            doc_id,
            text=row["text"],
            metadata=metadata,
            compute_embedding=row.get("compute_embedding", True),
        )
        cluster_counts[cluster_id] += 1

    total_chunks = sum(cluster_counts.values())
    print(
        f"[info] Loaded {total_chunks} chunks across {len(cluster_counts)} clusters "
        f"into library {library.id}"
    )

    if args.build_index:
        params = {"trees": args.trees, "leaf_size": args.leaf_size, "seed": args.seed}
        cli.build_index(
            library.id,
            algo=args.algo,
            metric=args.metric,
            params=params,
        )
        print(
            "[info] Index build triggered with "
            f"algo={args.algo} metric={args.metric} params={params}"
        )


if __name__ == "__main__":
    main()
