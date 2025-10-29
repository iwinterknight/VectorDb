from __future__ import annotations

import logging
from heapq import nlargest
from uuid import UUID

from app.domain.dtos import SearchRequest, SearchHit
from app.domain.errors import BadRequestError, NotFoundError
from app.repo.indices.flat import FlatIndex
from app.repo.indices.metrics import cosine, l2sq
from app.repo.memory import InMemoryRepo
from app.services.embeddings import EmbeddingProvider
from app.services.filters import match_obj
from app.services.indexing import IndexingService

log = logging.getLogger("vectordb")


class SearchService:
    def __init__(self, repo: InMemoryRepo, embedder: EmbeddingProvider, indexer: IndexingService):
        self.repo = repo
        self.embedder = embedder
        self.indexer = indexer
        # Keep a lazy flat index for "auto" fallback if none built yet:
        self._lazy_flat: dict[UUID, FlatIndex] = {}

    def _ensure_query_vec(self, lib_id: UUID, req: SearchRequest) -> list[float]:
        if req.query_embedding is not None:
            q = req.query_embedding
        else:
            if not req.query_text:
                raise BadRequestError("Provide query_text or query_embedding")
            q = self.embedder.embed([req.query_text])[0]
        # dimension check handled by ensure_dim in Day-1 code (still applicable)
        from app.services.validation import ensure_dim
        ensure_dim(self.repo, lib_id, q)
        return q

    def _score_metric(self, metric: str, q: list[float], v: list[float]) -> float:
        return cosine(q, v) if metric == "cosine" else -l2sq(q, v)

    def _prefilter_ids(self, lib_id: UUID, filters) -> set:
        """Return a set of chunk ids (UUIDs) that pass filters, or all if no filters."""
        if not filters:
            # no filtering
            s: set = set()
            for doc_id in self.repo.by_library_docs.get(lib_id, set()):
                s.update(self.repo.by_document_chunks.get(doc_id, set()))
            return s

        allowed: set = set()
        lib = self.repo.libraries[lib_id]
        for doc_id in self.repo.by_library_docs.get(lib_id, set()):
            doc = self.repo.documents[doc_id]
            doc_ok = match_obj(doc, filters.document or {})
            lib_ok = match_obj(lib, filters.library or {})
            for cid in self.repo.by_document_chunks.get(doc_id, set()):
                c = self.repo.chunks[cid]
                if doc_ok and lib_ok and match_obj(c, filters.chunk or {}):
                    allowed.add(cid)
        return allowed

    def _rank_over_ids(self, ids: list[str], q: list[float], metric: str) -> list[tuple[str, float]]:
        # exact scoring over provided chunk ids
        scored = []
        for sid in ids:
            cid = UUID(sid)
            v = self.repo.chunks[cid].embedding
            if v is None:
                continue
            scored.append((sid, self._score_metric(metric, q, v)))
        return scored

    def _lazy_build_flat_for(self, lib_id: UUID, metric: str) -> FlatIndex:
        pairs = []
        for doc_id in self.repo.by_library_docs.get(lib_id, set()):
            for cid in self.repo.by_document_chunks.get(doc_id, set()):
                c = self.repo.chunks[cid]
                if c.embedding is not None:
                    pairs.append((str(c.id), c.embedding))
        flat = self._lazy_flat.get(lib_id)
        if flat is None:
            flat = FlatIndex(metric=metric)
            self._lazy_flat[lib_id] = flat
        flat.rebuild(pairs)
        return flat

    def search(self, lib_id: UUID, req: SearchRequest) -> list[SearchHit]:
        if lib_id not in self.repo.libraries:
            raise NotFoundError("Library")

        lock = self.repo.get_lock(lib_id)
        lock.acquire_read()
        try:
            q = self._ensure_query_vec(lib_id, req)

            # Strict selection: honor requested algo exactly
            if req.algo == "flat":
                kind, inst = self.indexer.get_available_index(lib_id, prefer="flat")
                if kind != "flat" or inst is None:
                    idx = self._lazy_build_flat_for(lib_id, req.metric)  # build exact flat
                else:
                    idx = inst
                algo = "flat"

            elif req.algo == "rp":
                kind, inst = self.indexer.get_available_index(lib_id, prefer="rp")
                if kind != "rp" or inst is None:
                    raise BadRequestError("Requested RP index not built. Build it via /index:build")
                idx = inst
                algo = "rp"

            else:  # "auto"
                algo, idx = self.indexer.get_available_index(lib_id, prefer=None)
                if idx is None:
                    idx = self._lazy_build_flat_for(lib_id, req.metric)
                    algo = "flat"

            # Apply filters (pre-compute sets for both paths)
            allowed_ids_set = self._prefilter_ids(lib_id, req.filters)
            allowed_str = {str(i) for i in allowed_ids_set} if allowed_ids_set else None

            log.info(f"[search.select] idx_service_id={id(self.indexer)} algo={algo} idx_id={id(idx)}")

            # Query plan:
            # - flat exact: if filters present, rank only allowed ids for exactness
            # - rp ann: get top-k over ANN candidates (candidate pool size logged within RP), then filter + rerank
            if algo == "flat":
                if req.filters:
                    # Rank only over allowed ids (exact)
                    ids = [sid for sid in idx.ids if UUID(sid) in allowed_ids_set]
                    scored = self._rank_over_ids(ids, q, req.metric)
                    topk = nlargest(req.k, scored, key=lambda t: t[1])
                else:
                    topk = idx.query(q, req.k)
            else:
                # rp: ann candidates then optional filter + rerank
                cand = idx.query(q, req.k)
                log.info(f"[search] rp candidates returned={len(cand)}")
                if req.filters:
                    cand = [(cid, sc) for (cid, sc) in cand if (allowed_str is None or cid in allowed_str)]
                topk = nlargest(req.k, cand, key=lambda t: t[1])

            out: list[SearchHit] = []
            for cid, score in topk:
                c = self.repo.chunks[UUID(cid)]
                out.append(SearchHit(
                    chunk_id=str(c.id),
                    document_id=str(c.document_id),
                    library_id=str(c.library_id),
                    score=float(score),
                    text=c.text
                ))
            return out
        finally:
            lock.release_read()
