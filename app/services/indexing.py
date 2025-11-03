# app/services/indexing.py
from __future__ import annotations
import logging
from datetime import datetime, timezone
from typing import Any, Literal, Optional
from uuid import UUID

from app.repo.memory import InMemoryRepo
from app.repo.indices.flat import FlatIndex
from app.repo.indices.rp_forest import RPForestIndex
from app.domain.models import IndexAlgo, IndexState
from app.domain.errors import NotFoundError

# Optional (type only): avoid importing DiskStore at runtime to keep deps light
try:
    from app.persistence.store import DiskStore
except Exception:
    DiskStore = object  # type: ignore

log = logging.getLogger("vectordb")


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

    def build(
        self,
        lib_id: UUID,
        algo: Literal["flat","rp"],
        metric: Literal["cosine","l2"],
        params: dict,
        *,
        persist: bool = True,
        update_state: bool = True,
    ):
        if lib_id not in self.repo.libraries:
            raise NotFoundError("Library")
        if persist and not update_state:
            raise ValueError("persist cannot be True when update_state is False")

        lock = self.repo.get_lock(lib_id)
        lock.acquire_write()
        try:
            params_copy = dict(params or {})
            size = self._create_index(lib_id, algo, metric, params_copy)

            if update_state:
                lib = self.repo.libraries[lib_id]
                algo_enum = IndexAlgo(algo)
                state = IndexState(
                    built=True,
                    algo=algo_enum,
                    metric=metric,
                    params=params_copy,
                    size=size,
                    last_built_at=datetime.now(timezone.utc),
                )
                states_map = dict(lib.index_states)
                states_map[algo_enum.value] = state
                lib.index_state = state
                lib.index_states = states_map
                self.repo.libraries[lib_id] = lib

                if persist and self.store is not None:
                    self.store.append_wal({
                        "ts": datetime.now(timezone.utc).isoformat().replace("+00:00","Z"),
                        "op": "library.index_state",
                        "library_id": str(lib_id),
                        "index_state": state.model_dump(mode="json"),
                        "index_states": {
                            key: idx_state.model_dump(mode="json")
                            for key, idx_state in states_map.items()
                        },
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

    def restore_all_indices(self) -> dict[UUID, dict[str, int]]:
        """
        Rebuild in-memory indices for libraries whose IndexState marks them as built.
        Returns a mapping of library_id -> {algo: rebuilt_size}.
        """
        restored: dict[UUID, dict[str, int]] = {}
        for lib_id, lib in self.repo.libraries.items():
            states_map = dict(lib.index_states)
            # Backwards compatibility: if map empty fall back to single index_state
            if not states_map and lib.index_state.built and lib.index_state.algo:
                algo_key = lib.index_state.algo.value if isinstance(lib.index_state.algo, IndexAlgo) else lib.index_state.algo
                if algo_key:
                    states_map[algo_key] = lib.index_state

            for algo_key, state in states_map.items():
                if not state.built:
                    continue
                params = dict(state.params or {})
                try:
                    size = self.build(
                        lib_id,
                        algo_key,  # type: ignore[arg-type]
                        state.metric,
                        params,
                        persist=False,
                        update_state=False,
                    )
                    restored.setdefault(lib_id, {})[algo_key] = size
                except Exception as exc:
                    log.exception("[index] failed to restore %s index for library %s", algo_key, lib_id, exc_info=exc)
        if restored:
            log.info(
                "[index] restored indices: %s",
                ", ".join(
                    f"{lib_id}:{'/'.join(f'{algo}={size}' for algo, size in algos.items())}"
                    for lib_id, algos in restored.items()
                ),
            )
        return restored

    def _create_index(
        self,
        lib_id: UUID,
        algo: Literal["flat","rp"],
        metric: Literal["cosine","l2"],
        params: dict,
    ) -> int:
        pairs = list(self._pairs_for_library(lib_id))
        size = len(pairs)

        if algo == "flat":
            idx = FlatIndex(metric=metric)
            idx.rebuild(pairs)
            self.flat_indices[lib_id] = idx
        elif algo == "rp":
            trees = int(params.get("trees", 8))
            leaf_size = int(params.get("leaf_size", 64))
            seed = int(params.get("seed", 42))
            candidate_mult = float(params.get("candidate_mult", 2.0))
            idx = RPForestIndex(
                metric=metric,
                trees=trees,
                leaf_size=leaf_size,
                seed=seed,
                candidate_mult=candidate_mult,
            )
            idx.rebuild(pairs)
            self.rp_indices[lib_id] = idx
        else:
            raise ValueError("Unknown algo")

        return size

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
