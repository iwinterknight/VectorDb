from fastapi import APIRouter, Depends
from uuid import UUID
from app.domain.dtos import SearchRequest
from app.repo.memory import InMemoryRepo
from app.services.search import SearchService
from app.services.embeddings import StubEmbeddingProvider
from app.singletons import get_repo, get_indexer

router = APIRouter(prefix="/v1/libraries/{lib_id}", tags=["search"])

repo_singleton = get_repo()
indexer_singleton = get_indexer()

def get_search_service(
    repo: InMemoryRepo = Depends(lambda: repo_singleton)
) -> SearchService:
    embedder = StubEmbeddingProvider()
    indexer = indexer_singleton
    return SearchService(repo, embedder, indexer)

@router.post("/search")
def search(lib_id: UUID, body: SearchRequest, svc: SearchService = Depends(get_search_service)):
    return svc.search(lib_id, body)
