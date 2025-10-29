from __future__ import annotations
from uuid import UUID
from typing import Literal
from app.repo.memory import InMemoryRepo
from app.services.validation import ensure_dim
from app.domain.errors import BadRequestError, NotFoundError
from app.repo.indices.flat import FlatIndex
from app.services.embeddings import EmbeddingProvider
from app.domain.dtos import SearchRequest, SearchHit

class SearchService:
    def __init__(self, repo: InMemoryRepo, embedder: EmbeddingProvider):
        self.repo = repo
        self.embedder = embedder
        self.flat_indices: dict[UUID, FlatIndex] = {}

    def rebuild_flat(self, lib_id: UUID, metric: Literal["cosine","l2"]="cosine"):
        idx = FlatIndex(metric=metric)
        pairs = []
        for doc_id in self.repo.by_library_docs.get(lib_id, set()):
            for cid in self.repo.by_document_chunks.get(doc_id, set()):
                c = self.repo.chunks[cid]
                if c.embedding is not None:
                    pairs.append((str(c.id), c.embedding))
        idx.rebuild(pairs)
        self.flat_indices[lib_id] = idx
        return len(pairs)

    def search(self, lib_id: UUID, req: SearchRequest) -> list[SearchHit]:
        if lib_id not in self.repo.libraries:
            raise NotFoundError("Library")

        lock = self.repo.get_lock(lib_id)
        lock.acquire_read()
        try:
            idx = self.flat_indices.get(lib_id)
            if idx is None:
                self.rebuild_flat(lib_id, metric=req.metric)
                idx = self.flat_indices[lib_id]

            if req.query_embedding is not None:
                q = req.query_embedding
            else:
                if not req.query_text:
                    raise BadRequestError("Provide query_text or query_embedding")
                q = self.embedder.embed([req.query_text])[0]

            ensure_dim(self.repo, lib_id, q)
            results = idx.query(q, req.k)
            out: list[SearchHit] = []
            for cid, score in results:
                c = self.repo.chunks[UUID(cid)]
                out.append(SearchHit(
                    chunk_id=str(c.id), document_id=str(c.document_id),
                    library_id=str(c.library_id), score=float(score), text=c.text
                ))
            return out
        finally:
            lock.release_read()
