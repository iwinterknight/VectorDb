from __future__ import annotations
from uuid import UUID
from app.domain.models import Document
from app.repo.memory import InMemoryRepo

class DocumentService:
    def __init__(self, repo: InMemoryRepo):
        self.repo = repo

    def create(self, lib_id: UUID, title: str) -> Document:
        doc = Document(library_id=lib_id, title=title)
        self.repo.documents[doc.id] = doc
        self.repo.by_library_docs.setdefault(lib_id, set()).add(doc.id)
        self.repo.by_document_chunks[doc.id] = set()
        return doc

    def list(self, lib_id: UUID) -> list[Document]:
        ids = self.repo.by_library_docs.get(lib_id, set())
        return [self.repo.documents[i] for i in ids]

    def get(self, doc_id: UUID) -> Document:
        return self.repo.documents[doc_id]

    def update(self, doc_id: UUID, title: str | None) -> Document:
        d = self.get(doc_id)
        if title is not None:
            d.title = title
        return d

    def delete(self, lib_id: UUID, doc_id: UUID):
        for cid in list(self.repo.by_document_chunks.get(doc_id, [])):
            self.repo.chunks.pop(cid, None)
        self.repo.by_document_chunks.pop(doc_id, None)
        self.repo.by_library_docs.get(lib_id, set()).discard(doc_id)
        self.repo.documents.pop(doc_id, None)
