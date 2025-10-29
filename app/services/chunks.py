from __future__ import annotations
from uuid import UUID
from app.services.validation import ensure_dim
from app.domain.errors import NotFoundError
from app.domain.models import Chunk, ChunkMeta
from app.repo.memory import InMemoryRepo
from app.services.embeddings import EmbeddingProvider

class ChunkService:
    def __init__(self, repo: InMemoryRepo, embedder: EmbeddingProvider):
        self.repo = repo
        self.embedder = embedder

    def create(self, lib_id: UUID, doc_id: UUID, text: str,
               metadata: dict | None, compute_embedding: bool) -> Chunk:
        if doc_id not in self.repo.documents:
            raise NotFoundError("Document")
        if lib_id not in self.repo.libraries:
            raise NotFoundError("Library")
        meta = ChunkMeta(**(metadata or {}))
        chunk = Chunk(library_id=lib_id, document_id=doc_id, text=text, metadata=meta)
        if compute_embedding:
            emb = self.embedder.embed([text])[0]
            ensure_dim(self.repo, lib_id, emb)
            chunk.embedding = emb
        self.repo.chunks[chunk.id] = chunk
        self.repo.by_document_chunks.setdefault(doc_id, set()).add(chunk.id)
        self.repo.documents[doc_id].chunk_ids.append(chunk.id)
        return chunk

    def list(self, doc_id: UUID) -> list[Chunk]:
        ids = self.repo.by_document_chunks.get(doc_id, set())
        return [self.repo.chunks[i] for i in ids]

    def get(self, chunk_id: UUID) -> Chunk:
        return self.repo.chunks[chunk_id]

    def update(self, chunk_id: UUID, text: str | None) -> Chunk:
        c = self.get(chunk_id)
        if text is not None:
            c.text = text
            emb = self.embedder.embed([text])[0]
            ensure_dim(self.repo, c.library_id, emb)
            c.embedding = emb
        return c

    def delete(self, doc_id: UUID, chunk_id: UUID):
        self.repo.by_document_chunks.get(doc_id, set()).discard(chunk_id)
        self.repo.documents[doc_id].chunk_ids = [i for i in self.repo.documents[doc_id].chunk_ids if i != chunk_id]
        self.repo.chunks.pop(chunk_id, None)
