from fastapi import APIRouter, Depends
from uuid import UUID
from app.domain.dtos import SearchRequest, RerankRequest
from app.repo.memory import InMemoryRepo
from app.services.search import SearchService
from app.services.embeddings import EmbeddingProvider
from app.singletons import get_repo, get_indexer, get_embedder

router = APIRouter(prefix="/v1/libraries/{lib_id}", tags=["search"])

repo_singleton = get_repo()
indexer_singleton = get_indexer()

def get_search_service(
    repo: InMemoryRepo = Depends(get_repo),
    embedder: EmbeddingProvider = Depends(get_embedder),
    indexer = Depends(get_indexer),
) -> SearchService:
    return SearchService(repo, embedder, indexer)

@router.post("/search")
def search(lib_id: UUID, body: SearchRequest, svc: SearchService = Depends(get_search_service)):
    return svc.search(lib_id, body)


@router.post("/search/rerank")
def rerank(lib_id: UUID, body: RerankRequest, svc: SearchService = Depends(get_search_service)):
    return svc.rerank(lib_id, body)
