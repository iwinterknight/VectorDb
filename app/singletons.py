# app/singletons.py
from __future__ import annotations
import logging

from app.repo.memory import InMemoryRepo
from app.services.indexing import IndexingService
from app.services.embeddings import StubEmbeddingProvider
from app.persistence.store import DiskStore

log = logging.getLogger("vectordb")

# singletons
repo_singleton = InMemoryRepo()
store_singleton = DiskStore()           # or DiskStore("/data")
indexer_singleton = IndexingService(repo_singleton, store=store_singleton)
embedder_singleton = StubEmbeddingProvider()

def get_repo() -> InMemoryRepo: return repo_singleton
def get_indexer() -> IndexingService: return indexer_singleton
def get_embedder() -> StubEmbeddingProvider: return embedder_singleton
def get_store() -> DiskStore: return store_singleton

def bootstrap_from_disk() -> None:
    loaded = store_singleton.load()
    snap = loaded.get("snapshot")
    wal = loaded.get("wal", [])
    if snap:
        log.info(f"[persistence] loading snapshot with {len(snap.get('libraries',{}))} libs")
        repo_singleton.hydrate(snap)
    if wal:
        log.info(f"[persistence] replaying WAL entries: {len(wal)}")
        for e in wal:
            repo_singleton.apply_wal_entry(e)
