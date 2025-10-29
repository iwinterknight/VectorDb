from fastapi import APIRouter, Depends, HTTPException, status
from uuid import UUID
from app.domain.errors import NotFoundError
from app.domain.dtos import CreateDocumentIn, UpdateDocumentIn
from app.repo.memory import InMemoryRepo
from app.services.documents import DocumentService
from app.api.libraries import repo_singleton  # reuse

router = APIRouter(prefix="/v1/libraries/{lib_id}/documents", tags=["documents"])

def get_doc_service(repo: InMemoryRepo = Depends(lambda: repo_singleton)) -> DocumentService:
    return DocumentService(repo)

@router.post("", status_code=status.HTTP_201_CREATED)
def create_document(lib_id: UUID, body: CreateDocumentIn, svc: DocumentService = Depends(get_doc_service)):
    return svc.create(lib_id, body.title)

@router.get("")
def list_documents(lib_id: UUID, svc: DocumentService = Depends(get_doc_service)):
    return svc.list(lib_id)

@router.get("/{doc_id}")
def get_document(doc_id: UUID, svc: DocumentService = Depends(get_doc_service)):
    try:
        return svc.get(doc_id)
    except KeyError:
        raise NotFoundError("Document")

@router.patch("/{doc_id}")
def update_document(doc_id: UUID, body: UpdateDocumentIn, svc: DocumentService = Depends(get_doc_service)):
    try:
        return svc.update(doc_id, body.title)
    except KeyError:
        raise HTTPException(status_code=404, detail="Document not found")

@router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(lib_id: UUID, doc_id: UUID, svc: DocumentService = Depends(get_doc_service)):
    svc.delete(lib_id, doc_id)
