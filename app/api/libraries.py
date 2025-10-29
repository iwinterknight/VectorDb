from fastapi import APIRouter, Depends, HTTPException, status
from uuid import UUID
from app.domain.dtos import CreateLibraryIn, UpdateLibraryIn
from app.repo.memory import InMemoryRepo
from app.services.libraries import LibraryService

router = APIRouter(prefix="/v1/libraries", tags=["libraries"])

def get_lib_service(repo: InMemoryRepo = Depends(lambda: repo_singleton)) -> LibraryService:
    return LibraryService(repo)

# wire a module-level singleton repo for Day 1
from app.repo.memory import InMemoryRepo
repo_singleton = InMemoryRepo()

@router.post("", status_code=status.HTTP_201_CREATED)
def create_library(body: CreateLibraryIn, svc: LibraryService = Depends(get_lib_service)):
    lib = svc.create(name=body.name, description=body.description)
    return lib

@router.get("")
def list_libraries(svc: LibraryService = Depends(get_lib_service)):
    return svc.list()

@router.get("/{lib_id}")
def get_library(lib_id: UUID, svc: LibraryService = Depends(get_lib_service)):
    try:
        return svc.get(lib_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Library not found")

@router.patch("/{lib_id}")
def update_library(lib_id: UUID, body: UpdateLibraryIn, svc: LibraryService = Depends(get_lib_service)):
    try:
        return svc.update(lib_id, body.name, body.description)
    except KeyError:
        raise HTTPException(status_code=404, detail="Library not found")

@router.delete("/{lib_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_library(lib_id: UUID, svc: LibraryService = Depends(get_lib_service)):
    svc.delete(lib_id)
