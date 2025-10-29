from __future__ import annotations
from uuid import UUID
from datetime import datetime, timezone
from app.domain.models import Library, IndexState
from app.repo.memory import InMemoryRepo

class LibraryService:
    def __init__(self, repo: InMemoryRepo):
        self.repo = repo

    def create(self, name: str, description: str | None) -> Library:
        lib = Library(name=name, description=description)
        self.repo.libraries[lib.id] = lib
        self.repo.by_library_docs[lib.id] = set()
        self.repo.get_lock(lib.id)  # initialize lock
        return lib

    def get(self, lib_id: UUID) -> Library:
        return self.repo.libraries[lib_id]

    def list(self) -> list[Library]:
        return list(self.repo.libraries.values())

    def update(self, lib_id: UUID, name: str | None, description: str | None) -> Library:
        lib = self.get(lib_id)
        if name is not None:
            lib.name = name
        if description is not None:
            lib.description = description
        return lib

    def delete(self, lib_id: UUID):
        # cascade delete docs + chunks
        doc_ids = list(self.repo.by_library_docs.get(lib_id, []))
        for did in doc_ids:
            for cid in list(self.repo.by_document_chunks.get(did, [])):
                self.repo.chunks.pop(cid, None)
            self.repo.by_document_chunks.pop(did, None)
            self.repo.documents.pop(did, None)
        self.repo.by_library_docs.pop(lib_id, None)
        self.repo.libraries.pop(lib_id, None)
        self.repo.locks.pop(lib_id, None)

    def mark_index_built(self, lib_id: UUID, algo: str, metric: str, size: int):
        lib = self.get(lib_id)
        lib.index_state = IndexState(
            built=True, algo=algo, metric=metric,
            params={}, size=size, last_built_at=datetime.now(timezone.utc)
        )
