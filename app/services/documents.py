# app/services/documents.py
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from app.domain.models import Document
from app.repo.memory import InMemoryRepo
from app.singletons import get_store

# Single DiskStore instance used for WAL appends
store = get_store()


class DocumentService:
    """
    Document CRUD with WAL persistence.
    Notes:
      - We WAL every successful in-memory mutation so crash recovery (snapshot + WAL replay)
        reproduces the same state.
      - Deleting a document cascades to its chunks; we emit WAL entries for each chunk.delete
        before the document.delete so replay order is consistent.
    """
    def __init__(self, repo: InMemoryRepo):
        self.repo = repo

    # ---- CREATE ----
    def create(self, lib_id: UUID, title: str, metadata: dict | None = None) -> Document:
        doc = Document(library_id=lib_id, title=title, metadata=metadata or {})
        # in-memory mutation
        self.repo.documents[doc.id] = doc
        self.repo.by_library_docs.setdefault(lib_id, set()).add(doc.id)
        self.repo.by_document_chunks[doc.id] = set()

        # WAL append AFTER successful in-memory change
        store.append_wal({
            "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "op": "document.create",
            "data": doc.model_dump(mode="json"),
        })
        return doc

    # ---- LIST / GET ----
    def list(self, lib_id: UUID) -> list[Document]:
        ids = self.repo.by_library_docs.get(lib_id, set())
        return [self.repo.documents[i] for i in ids]

    def get(self, doc_id: UUID) -> Document:
        return self.repo.documents[doc_id]

    # ---- UPDATE ----
    def update(self, doc_id: UUID, title: str | None = None, metadata: dict | None = None) -> Document:
        d = self.get(doc_id)

        patch: dict = {}
        if title is not None and title != d.title:
            d.title = title
            patch["title"] = title
        if metadata is not None and metadata != getattr(d, "metadata", {}):
            d.metadata = metadata
            patch["metadata"] = metadata

        # Only WAL if something actually changed
        if patch:
            store.append_wal({
                "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "op": "document.update",
                "id": str(doc_id),
                "data": patch,
            })
        return d

    # ---- DELETE (cascades chunks) ----
    def delete(self, lib_id: UUID, doc_id: UUID) -> None:
        """
        Cascade delete order:
          1) chunks of the document (emit chunk.delete for each)
          2) the document itself (document.delete)
        Keep repo indices in sync (by_document_chunks, by_library_docs).
        """
        # Collect chunk ids first
        chunk_ids = list(self.repo.by_document_chunks.get(doc_id, []))

        # 1) delete chunks (in-memory + WAL per chunk)
        for cid in chunk_ids:
            c = self.repo.chunks.pop(cid, None)
            if c is not None:
                # update secondary map
                s = self.repo.by_document_chunks.get(doc_id)
                if s and cid in s:
                    s.remove(cid)
                # WAL
                store.append_wal({
                    "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                    "op": "chunk.delete",
                    "id": str(cid),
                })

        # Clean the document->chunks map
        self.repo.by_document_chunks.pop(doc_id, None)

        # 2) remove from by_library_docs and documents map
        self.repo.by_library_docs.get(lib_id, set()).discard(doc_id)
        self.repo.documents.pop(doc_id, None)

        # WAL for document deletion
        store.append_wal({
            "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "op": "document.delete",
            "id": str(doc_id),
        })
