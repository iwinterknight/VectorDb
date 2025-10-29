from __future__ import annotations
from threading import RLock, Condition
from typing import Dict
from uuid import UUID
from app.domain.models import Library, Document, Chunk

class RWLock:
    def __init__(self):
        self._lock = RLock()
        self._readers = 0
        self._cond = Condition(self._lock)

    def acquire_read(self):
        with self._lock:
            self._readers += 1

    def release_read(self):
        with self._lock:
            self._readers -= 1
            if self._readers == 0:
                self._cond.notify_all()

    def acquire_write(self):
        self._lock.acquire()
        while self._readers > 0:
            self._cond.wait()

    def release_write(self):
        self._lock.release()

class InMemoryRepo:
    def __init__(self):
        self.libraries: Dict[UUID, Library] = {}
        self.documents: Dict[UUID, Document] = {}
        self.chunks: Dict[UUID, Chunk] = {}
        self.by_library_docs: Dict[UUID, set[UUID]] = {}
        self.by_document_chunks: Dict[UUID, set[UUID]] = {}
        self.locks: Dict[UUID, RWLock] = {}

    def get_lock(self, lib_id: UUID) -> RWLock:
        if lib_id not in self.locks:
            self.locks[lib_id] = RWLock()
        return self.locks[lib_id]
