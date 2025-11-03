from __future__ import annotations
from threading import RLock, Condition
from typing import Dict
from uuid import UUID
from typing import Any
from app.domain.models import Library, Document, Chunk, IndexState, IndexAlgo

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

    # ---------- (A) serialization ----------
    def dump_json(self) -> dict[str, Any]:
        """Serialize full repo to JSON-friendly dict."""
        libs = {str(k): v.model_dump(mode="json") for k, v in self.libraries.items()}
        docs = {str(k): v.model_dump(mode="json") for k, v in self.documents.items()}
        chks = {str(k): v.model_dump(mode="json") for k, v in self.chunks.items()}

        return {
            "schema_version": 1,
            "libraries": libs,
            "documents": docs,
            "chunks": chks,
        }

    # ---------- (B) hydrate from snapshot ----------
    def hydrate(self, image: dict[str, Any]) -> None:
        """Replace in-memory state with a snapshot image."""
        self.libraries.clear()
        self.documents.clear()
        self.chunks.clear()
        self.by_library_docs.clear()
        self.by_document_chunks.clear()
        self.locks.clear()

        if not image:
            return

        for sid, ld in (image.get("libraries") or {}).items():
            lid = UUID(sid)
            lib = Library(**ld)
            # Ensure legacy snapshots populate index_states from index_state
            if lib.index_state.built and lib.index_state.algo and not lib.index_states:
                algo_key = lib.index_state.algo.value if isinstance(lib.index_state.algo, IndexAlgo) else lib.index_state.algo
                if algo_key:
                    lib.index_states = {algo_key: lib.index_state}
            self.libraries[lid] = lib
            # ensure per-library lock exists
            self.get_lock(lid)

        for sid, dd in (image.get("documents") or {}).items():
            did = UUID(sid)
            self.documents[did] = Document(**dd)
            self.by_library_docs.setdefault(self.documents[did].library_id, set()).add(did)

        for sid, cd in (image.get("chunks") or {}).items():
            cid = UUID(sid)
            self.chunks[cid] = Chunk(**cd)
            doc_id = self.chunks[cid].document_id
            self.by_document_chunks.setdefault(doc_id, set()).add(cid)

    # ---------- (C) WAL replay ----------
    def apply_wal_entry(self, entry: dict[str, Any]) -> None:
        """Apply one WAL op directly to in-memory structures (no WAL here!)."""
        op = entry.get("op")
        data = entry.get("data")
        if op == "library.create":
            lib = Library(**data);
            self.libraries[lib.id] = lib;
            self.get_lock(lib.id)
        elif op == "library.update":
            lid = UUID(entry["id"]);
            cur = self.libraries[lid];
            patched = {**cur.model_dump(), **data}
            self.libraries[lid] = Library(**patched)
        elif op == "library.delete":
            lid = UUID(entry["id"])
            # NOTE: keep it simple; caller should have enforced emptiness
            self.libraries.pop(lid, None)
            self.by_library_docs.pop(lid, None)
            self.locks.pop(lid, None)

        elif op == "document.create":
            doc = Document(**data)
            self.documents[doc.id] = doc
            self.by_library_docs.setdefault(doc.library_id, set()).add(doc.id)
        elif op == "document.update":
            did = UUID(entry["id"])
            cur = self.documents[did];
            patched = {**cur.model_dump(), **data}
            self.documents[did] = Document(**patched)
        elif op == "document.delete":
            did = UUID(entry["id"])
            self.documents.pop(did, None)
            self.by_document_chunks.pop(did, None)

        elif op == "chunk.create":
            chk = Chunk(**data)
            self.chunks[chk.id] = chk
            self.by_document_chunks.setdefault(chk.document_id, set()).add(chk.id)
        elif op == "chunk.update":
            cid = UUID(entry["id"])
            cur = self.chunks[cid];
            patched = {**cur.model_dump(), **data}
            self.chunks[cid] = Chunk(**patched)
        elif op == "chunk.delete":
            cid = UUID(entry["id"])
            c = self.chunks.pop(cid, None)
            if c:
                s = self.by_document_chunks.get(c.document_id)
                if s and cid in s: s.remove(cid)

        elif op == "library.index_state":
            lid = UUID(entry["library_id"])
            st = IndexState(**entry["index_state"])
            lib = self.libraries[lid]
            lib.index_state = st
            states_map = dict(lib.index_states)
            entry_states = entry.get("index_states")
            if entry_states:
                for algo_key, state_data in entry_states.items():
                    states_map[str(algo_key)] = IndexState(**state_data)
            else:
                algo_key = st.algo.value if isinstance(st.algo, IndexAlgo) else st.algo
                if algo_key:
                    states_map[str(algo_key)] = st
            lib.index_states = states_map
            self.libraries[lid] = lib
        else:
            # unknown op; ignore safely
            pass
