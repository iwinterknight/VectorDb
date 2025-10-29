from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from app.repo.memory import InMemoryRepo
from app.repo.indices.flat import FlatIndex
from app.repo.indices.rp_forest import RPForestIndex
from app.domain.models import IndexState
from app.domain.errors import NotFoundError

log = logging.getLogger("vectordb")

class IndexingService:
    """
    Manages per-library indices and safe build/swap under write lock.
    """
    def __init__(self, repo: InMemoryRepo):
        self.repo = repo
        self.flat_indices: dict[UUID, FlatIndex] = {}
        self.rp_indices: dict[UUID, RPForestIndex] = {}

    def _pairs_for_library(self, lib_id: UUID):
        # Returns (chunk_id, embedding) for all embedded chunks in library
        for doc_id in self.repo.by_library_docs.get(lib_id, set()):
            for cid in self.repo.by_document_chunks.get(doc_id, set()):
                c = self.repo.chunks[cid]
                if c.embedding is not None:
                    yield (str(c.id), c.embedding)

    def build(self, lib_id: UUID, algo: Literal["flat","rp"], metric: Literal["cosine","l2"], params: dict):
        if lib_id not in self.repo.libraries:
            raise NotFoundError("Library")
        lock = self.repo.get_lock(lib_id)
        lock.acquire_write()
        try:
            pairs = list(self._pairs_for_library(lib_id))
            size = len(pairs)

            if algo == "flat":
                idx = FlatIndex(metric=metric)
                idx.rebuild(pairs)
                # atomic swap
                self.flat_indices[lib_id] = idx
                log.info(f"[index.build] idx_service_id={id(self)} algo={algo} metric={metric} size={size} params={params}")
            elif algo == "rp":
                trees = int(params.get("trees", 8))
                leaf_size = int(params.get("leaf_size", 64))
                seed = int(params.get("seed", 42))
                candidate_mult = float(params.get("candidate_mult", 2.0))  # <-- NEW
                idx = RPForestIndex(metric=metric, trees=trees, leaf_size=leaf_size,
                                    seed=seed, candidate_mult=candidate_mult)  # <-- pass it
                idx.rebuild(pairs)
                self.rp_indices[lib_id] = idx
                log.info(f"[index.build] idx_service_id={id(self)} algo={algo} metric={metric} size={size} params={params}")
            else:
                raise ValueError("Unknown algo")

            # update library index state (simple: reflect the last built index)
            lib = self.repo.libraries[lib_id]
            lib.index_state = IndexState(
                built=True, algo=algo, metric=metric, params=params,
                size=size, last_built_at=datetime.now(timezone.utc)
            )
            return size
        finally:
            lock.release_write()

    def get_index_state(self, lib_id: UUID) -> IndexState:
        if lib_id not in self.repo.libraries:
            raise NotFoundError("Library")
        return self.repo.libraries[lib_id].index_state

    def get_available_index(self, lib_id: UUID, prefer: Literal["rp", "flat"] | None = None):
        """
        Returns (kind, instance). If 'prefer' is given, we only return that kind if available;
        otherwise (None, None). If 'prefer' is None, we choose best available (rp > flat).
        """
        rp = self.rp_indices.get(lib_id)
        fl = self.flat_indices.get(lib_id)

        if prefer == "rp":
            return ("rp", rp) if rp is not None else (None, None)
        if prefer == "flat":
            return ("flat", fl) if fl is not None else (None, None)

        # auto: prefer rp, then flat
        if rp is not None:
            return ("rp", rp)
        if fl is not None:
            return ("flat", fl)
        return (None, None)

    def get_live_index_params(self, lib_id: UUID) -> dict:
        out: dict = {"rp": None, "flat": None}
        rp = self.rp_indices.get(lib_id)
        if rp is not None:
            out["rp"] = {
                "trees": rp.trees,
                "leaf_size": rp.leaf_size,
                "seed": rp.seed,
                "candidate_mult": getattr(rp, "candidate_mult", None),
                "idx_id": id(rp),
            }
        fl = self.flat_indices.get(lib_id)
        if fl is not None:
            out["flat"] = {
                "metric": fl.metric,
                "size": len(getattr(fl, "ids", [])),
                "idx_id": id(fl),
            }
        return out
