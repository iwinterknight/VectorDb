# app/services/indexing.py
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Literal, Optional
from uuid import UUID

from app.repo.memory import InMemoryRepo
from app.repo.indices.flat import FlatIndex
from app.repo.indices.rp_forest import RPForestIndex
from app.domain.models import IndexState
from app.domain.errors import NotFoundError

# Optional (type only): avoid importing DiskStore at runtime to keep deps light
try:
    from app.persistence.store import DiskStore
except Exception:
    DiskStore = object  # type: ignore


class IndexingService:
    """
    Manages per-library indices and safe build/swap under write lock.
    Optionally persists index_state via a DiskStore (WAL) if provided.
    """
    def __init__(self, repo: InMemoryRepo, store: Optional[DiskStore] = None):
        self.repo = repo
        self.store = store
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
                self.flat_indices[lib_id] = idx
                # you may clear rp if you want to enforce single-active
            elif algo == "rp":
                trees = int(params.get("trees", 8))
                leaf_size = int(params.get("leaf_size", 64))
                seed = int(params.get("seed", 42))
                candidate_mult = float(params.get("candidate_mult", 2.0))
                idx = RPForestIndex(metric=metric, trees=trees, leaf_size=leaf_size,
                                    seed=seed, candidate_mult=candidate_mult)
                idx.rebuild(pairs)
                self.rp_indices[lib_id] = idx
            else:
                raise ValueError("Unknown algo")

            # update library index state
            lib = self.repo.libraries[lib_id]
            lib.index_state = IndexState(
                built=True,
                algo=algo,
                metric=metric,
                params=params,
                size=size,
                last_built_at=datetime.now(timezone.utc),
            )

            # WAL the index_state if a store is available
            if self.store is not None:
                self.store.append_wal({
                    "ts": datetime.now(timezone.utc).isoformat().replace("+00:00","Z"),
                    "op": "library.index_state",
                    "library_id": str(lib_id),
                    "index_state": lib.index_state.model_dump(mode="json"),
                })

            return size
        finally:
            lock.release_write()

    def get_index_state(self, lib_id: UUID) -> IndexState:
        if lib_id not in self.repo.libraries:
            raise NotFoundError("Library")
        return self.repo.libraries[lib_id].index_state

    def get_available_index(self, lib_id: UUID, prefer: Literal["rp","flat"] | None = None):
        rp = self.rp_indices.get(lib_id)
        fl = self.flat_indices.get(lib_id)
        if prefer == "rp" and rp is not None:
            return ("rp", rp)
        if prefer == "flat" and fl is not None:
            return ("flat", fl)
        if rp is not None:
            return ("rp", rp)
        if fl is not None:
            return ("flat", fl)
        return (None, None)

    def get_live_index_params(self, lib_id: UUID) -> dict[str, Any]:
        """
        Inspect current in-memory indices for a library.
        Returns shapes/params so you can verify which index is live after restart.
        (Note: indices are not persisted; this purely reflects RAM.)
        """
        if lib_id not in self.repo.libraries:
            raise NotFoundError("Library")

        rp = self.rp_indices.get(lib_id)
        fl = self.flat_indices.get(lib_id)

        out: dict[str, Any] = {"rp": None, "flat": None}

        if rp is not None:
            # Be tolerant if internals differ; getattr with defaults
            out["rp"] = {
                "trees": getattr(rp, "trees", None),
                "leaf_size": getattr(rp, "leaf_size", None),
                "seed": getattr(rp, "seed", None),
                "candidate_mult": getattr(rp, "candidate_mult", None),
                "metric": getattr(rp, "metric", None),
                "idx_id": id(rp),
            }

        if fl is not None:
            out["flat"] = {
                "metric": getattr(fl, "metric", None),
                "size": len(getattr(fl, "ids", [])),
                "idx_id": id(fl),
            }

        return out