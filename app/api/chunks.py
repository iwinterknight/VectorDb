from fastapi import APIRouter, Depends, HTTPException, status
from uuid import UUID
from app.domain.dtos import CreateChunkIn, UpdateChunkIn
from app.repo.memory import InMemoryRepo
from app.services.chunks import ChunkService
from app.services.embeddings import StubEmbeddingProvider
from app.api.libraries import repo_singleton

router = APIRouter(prefix="/v1/libraries/{lib_id}/documents/{doc_id}/chunks", tags=["chunks"])

def get_chunk_service(repo: InMemoryRepo = Depends(lambda: repo_singleton)) -> ChunkService:
    return ChunkService(repo, StubEmbeddingProvider())

@router.post("", status_code=status.HTTP_201_CREATED)
def create_chunk(lib_id: UUID, doc_id: UUID, body: CreateChunkIn, svc: ChunkService = Depends(get_chunk_service)):
    return svc.create(lib_id, doc_id, body.text, body.metadata, body.compute_embedding)

@router.get("")
def list_chunks(doc_id: UUID, svc: ChunkService = Depends(get_chunk_service)):
    return svc.list(doc_id)

@router.get("/{chunk_id}")
def get_chunk(chunk_id: UUID, svc: ChunkService = Depends(get_chunk_service)):
    try:
        return svc.get(chunk_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Chunk not found")

@router.patch("/{chunk_id}")
def update_chunk(chunk_id: UUID, body: UpdateChunkIn, svc: ChunkService = Depends(get_chunk_service)):
    try:
        return svc.update(chunk_id, body.text)
    except KeyError:
        raise HTTPException(status_code=404, detail="Chunk not found")

@router.delete("/{chunk_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_chunk(doc_id: UUID, chunk_id: UUID, svc: ChunkService = Depends(get_chunk_service)):
    svc.delete(doc_id, chunk_id)
