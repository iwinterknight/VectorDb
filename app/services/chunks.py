# app/services/chunks.py
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.services.validation import ensure_dim
from app.domain.errors import NotFoundError, BadRequestError
from app.domain.models import Chunk, ChunkMeta
from app.repo.memory import InMemoryRepo
from app.services.embeddings import EmbeddingProvider
from app.singletons import get_store

store = get_store()


class ChunkService:
    def __init__(self, repo: InMemoryRepo, embedder: EmbeddingProvider):
        self.repo = repo
        self.embedder = embedder

    # -------------------------
    # Create
    # -------------------------
    def create(
        self,
        lib_id: UUID,
        doc_id: UUID,
        text: str,
        metadata: dict | None,
        compute_embedding: bool,
    ) -> Chunk:
        if lib_id not in self.repo.libraries:
            raise NotFoundError("Library")
        if doc_id not in self.repo.documents:
            raise NotFoundError("Document")
        if self.repo.documents[doc_id].library_id != lib_id:
            raise BadRequestError("Document does not belong to library")

        # Acquire the library write lock for all mutations in this library
        lock = self.repo.get_lock(lib_id)
        lock.acquire_write()
        try:
            meta = ChunkMeta(**(metadata or {}))
            chunk = Chunk(library_id=lib_id, document_id=doc_id, text=text, metadata=meta)

            if compute_embedding:
                emb = self.embedder.embed([text])[0]
                ensure_dim(self.repo, lib_id, emb)
                chunk.embedding = emb

            # In-memory mutation
            self.repo.chunks[chunk.id] = chunk
            self.repo.by_document_chunks.setdefault(doc_id, set()).add(chunk.id)
            self.repo.documents[doc_id].chunk_ids.append(chunk.id)

            # WAL append (after successful in-memory mutation)
            store.append_wal({
                "ts": datetime.utcnow().isoformat() + "Z",
                "op": "chunk.create",
                "data": chunk.model_dump(mode="json")
            })

            return chunk
        finally:
            lock.release_write()

    # -------------------------
    # List / Get (reads)
    # -------------------------
    def list(self, doc_id: UUID) -> list[Chunk]:
        # For simplicity we do not take read locks here; if you added read locks,
        # you can mirror the search service pattern.
        ids = self.repo.by_document_chunks.get(doc_id, set())
        return [self.repo.chunks[i] for i in ids]

    def get(self, chunk_id: UUID) -> Chunk:
        if chunk_id not in self.repo.chunks:
            raise NotFoundError("Chunk")
        return self.repo.chunks[chunk_id]

    # -------------------------
    # Update (only 'text' for now)
    # -------------------------
    def update(self, chunk_id: UUID, text: str | None) -> Chunk:
        if chunk_id not in self.repo.chunks:
            raise NotFoundError("Chunk")

        c = self.repo.chunks[chunk_id]
        lib_id = c.library_id

        lock = self.repo.get_lock(lib_id)
        lock.acquire_write()
        try:
            # Refresh object in case it changed before we acquired the lock
            c = self.repo.chunks[chunk_id]

            if text is not None:
                c.text = text
                # Recompute embedding to keep search/index correct
                emb = self.embedder.embed([text])[0]
                ensure_dim(self.repo, lib_id, emb)
                c.embedding = emb

                # WAL with minimal patch (only fields we changed)
                store.append_wal({
                    "ts": datetime.utcnow().isoformat() + "Z",
                    "op": "chunk.update",
                    "id": str(chunk_id),
                    "data": {
                        "text": c.text,
                        "embedding": c.embedding,
                    }
                })

            return c
        finally:
            lock.release_write()

    # -------------------------
    # Delete
    # -------------------------
    def delete(self, doc_id: UUID, chunk_id: UUID) -> None:
        # Validate existence and derive library
        if doc_id not in self.repo.documents:
            raise NotFoundError("Document")
        if chunk_id not in self.repo.chunks:
            # idempotent delete: no-op if it doesn't exist
            return

        c = self.repo.chunks[chunk_id]
        lib_id = c.library_id

        if self.repo.documents[doc_id].library_id != lib_id:
            raise BadRequestError("Document does not belong to chunk's library")

        lock = self.repo.get_lock(lib_id)
        lock.acquire_write()
        try:
            # Double-check under lock
            c = self.repo.chunks.get(chunk_id)
            if not c:
                return

            # In-memory mutation
            self.repo.by_document_chunks.get(doc_id, set()).discard(chunk_id)
            if doc_id in self.repo.documents:
                self.repo.documents[doc_id].chunk_ids = [
                    i for i in self.repo.documents[doc_id].chunk_ids if i != chunk_id
                ]
            self.repo.chunks.pop(chunk_id, None)

            # WAL append
            store.append_wal({
                "ts": datetime.utcnow().isoformat() + "Z",
                "op": "chunk.delete",
                "id": str(chunk_id)
            })
        finally:
            lock.release_write()
