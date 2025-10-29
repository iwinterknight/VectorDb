from fastapi import APIRouter, Depends, status
from uuid import UUID

from app.domain.dtos import IndexBuildRequest, IndexStateOut
from app.repo.memory import InMemoryRepo
from app.services.indexing import IndexingService
from app.singletons import get_repo, get_indexer

router = APIRouter(prefix="/v1/libraries/{lib_id}/index", tags=["indexing"])

repo_singleton = get_repo()
indexer_singleton = get_indexer()

def get_indexer(repo: InMemoryRepo = Depends(lambda: repo_singleton)) -> IndexingService:
    return indexer_singleton

@router.post("/build", status_code=status.HTTP_202_ACCEPTED)
def build_index(lib_id: UUID, body: IndexBuildRequest, idx: IndexingService = Depends(get_indexer)):
    size = idx.build(lib_id, body.algo, body.metric, body.params or {})
    return {"status": "building-complete", "algo": body.algo, "metric": body.metric, "size": size}

@router.get("")
def get_index_state(lib_id: UUID, idx: IndexingService = Depends(get_indexer)) -> IndexStateOut:
    st = idx.get_index_state(lib_id)
    return st.model_dump(mode="json")

@router.get("/live")
def get_live_index(lib_id: UUID, idx: IndexingService = Depends(get_indexer)):
    return idx.get_live_index_params(lib_id)
