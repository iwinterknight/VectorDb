# app/singletons.py
from __future__ import annotations
import logging

from app.repo.memory import InMemoryRepo
from app.services.indexing import IndexingService
from app.services.embeddings import StubEmbeddingProvider, CohereEmbeddingProvider
from app.persistence.store import DiskStore
from app.config import settings

log = logging.getLogger("vectordb")

# singletons
repo_singleton = InMemoryRepo()
store_singleton = DiskStore()
indexer_singleton = IndexingService(repo_singleton, store=store_singleton)

if settings.embedding_provider.lower() == "cohere":
    embedder_singleton = CohereEmbeddingProvider()
    log.info("[embed] Using CohereEmbeddingProvider model=%s", settings.cohere_model)
else:
    embedder_singleton = StubEmbeddingProvider()
    log.info("[embed] Using StubEmbeddingProvider dim=%d", settings.embedding_dim)

def get_repo() -> InMemoryRepo: return repo_singleton
def get_indexer() -> IndexingService: return indexer_singleton
def get_store() -> DiskStore: return store_singleton
def get_embedder(): return embedder_singleton


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
    restored = indexer_singleton.restore_all_indices()
    if restored:
        details = ", ".join(
            f"{lib_id}:{'/'.join(f'{algo}={size}' for algo, size in algos.items())}"
            for lib_id, algos in restored.items()
        )
        log.info(f"[persistence] restored indices -> {details}")
