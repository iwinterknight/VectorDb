# app/services/libraries.py
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from app.domain.models import Library, IndexState
from app.repo.memory import InMemoryRepo
from app.singletons import get_store

# Single DiskStore instance used for WAL appends
store = get_store()


class LibraryService:
    """
    Library CRUD with WAL persistence.
    NOTE:
      - We persist ONLY entities (libraries/docs/chunks, incl. embeddings) via WAL+snapshot.
      - Indices are derived; we persist index_state and rebuild as needed.
    """
    def __init__(self, repo: InMemoryRepo):
        self.repo = repo

    # ---- CREATE ----
    def create(self, name: str, description: str | None) -> Library:
        lib = Library(name=name, description=description)
        # in-memory mutation
        self.repo.libraries[lib.id] = lib
        self.repo.by_library_docs[lib.id] = set()
        self.repo.get_lock(lib.id)  # initialize lock

        # WAL append AFTER successful in-memory change
        store.append_wal({
            "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "op": "library.create",
            "data": lib.model_dump(mode="json"),
        })
        return lib

    # ---- READ ----
    def get(self, lib_id: UUID) -> Library:
        return self.repo.libraries[lib_id]

    def list(self) -> list[Library]:
        return list(self.repo.libraries.values())

    # ---- UPDATE ----
    def update(self, lib_id: UUID, name: str | None, description: str | None) -> Library:
        lib = self.get(lib_id)

        patch: dict = {}
        if name is not None and name != lib.name:
            lib.name = name
            patch["name"] = name
        if description is not None and description != lib.description:
            lib.description = description
            patch["description"] = description

        # Only WAL if something actually changed
        if patch:
            store.append_wal({
                "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "op": "library.update",
                "id": str(lib_id),
                "data": patch,
            })
        return lib

    # ---- DELETE (cascades docs + chunks) ----
    def delete(self, lib_id: UUID):
        """
        Cascade delete order:
          1) chunks
          2) documents
          3) library
        We emit WAL entries for each entity deletion so WAL replay mirrors this sequence.
        """
        # Collect targets first (avoid mutating while iterating)
        doc_ids = list(self.repo.by_library_docs.get(lib_id, []))
        chunk_ids_in_order: list[UUID] = []
        for did in doc_ids:
            chunk_ids_in_order.extend(list(self.repo.by_document_chunks.get(did, [])))

        # 1) delete chunks (in-memory + WAL per chunk)
        for cid in chunk_ids_in_order:
            c = self.repo.chunks.pop(cid, None)
            if c is not None:
                s = self.repo.by_document_chunks.get(c.document_id)
                if s and cid in s:
                    s.remove(cid)
                store.append_wal({
                    "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                    "op": "chunk.delete",
                    "id": str(cid),
                })

        # 2) delete documents (in-memory + WAL per doc)
        for did in doc_ids:
            self.repo.documents.pop(did, None)
            self.repo.by_document_chunks.pop(did, None)
            store.append_wal({
                "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "op": "document.delete",
                "id": str(did),
            })

        # 3) delete library (in-memory + WAL)
        self.repo.by_library_docs.pop(lib_id, None)
        self.repo.libraries.pop(lib_id, None)
        self.repo.locks.pop(lib_id, None)

        store.append_wal({
            "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "op": "library.delete",
            "id": str(lib_id),
        })

    # ---- INDEX STATE (called by IndexingService after build) ----
    def mark_index_built(self, lib_id: UUID, algo: str, metric: str, size: int):
        """
        Update the persisted index_state to reflect the latest build,
        and WAL it so it survives restarts.
        """
        lib = self.get(lib_id)
        lib.index_state = IndexState(
            built=True,
            algo=algo,
            metric=metric,
            params={},  # IndexingService may pass actual params when calling this if desired
            size=size,
            last_built_at=datetime.now(timezone.utc),
        )

        # Persist index_state change
        store.append_wal({
            "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "op": "library.index_state",
            "library_id": str(lib_id),
            "index_state": lib.index_state.model_dump(mode="json"),
        })
