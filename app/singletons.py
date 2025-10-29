from app.repo.memory import InMemoryRepo
from app.services.indexing import IndexingService
from app.services.embeddings import StubEmbeddingProvider

# ONE repo for the whole process
repo_singleton = InMemoryRepo()

# ONE indexer that both /index and /search will use
indexer_singleton = IndexingService(repo_singleton)

# Embeddings (can keep a singleton; it's stateless)
embedder_singleton = StubEmbeddingProvider()

def get_repo() -> InMemoryRepo:
    return repo_singleton

def get_indexer() -> IndexingService:
    return indexer_singleton

def get_embedder() -> StubEmbeddingProvider:
    return embedder_singleton
