from pydantic import BaseModel
from typing import Any, Literal

class CreateLibraryIn(BaseModel):
    name: str
    description: str | None = None

class UpdateLibraryIn(BaseModel):
    name: str | None = None
    description: str | None = None

class CreateDocumentIn(BaseModel):
    title: str

class UpdateDocumentIn(BaseModel):
    title: str | None = None

class CreateChunkIn(BaseModel):
    text: str
    metadata: dict[str, Any] | None = None
    compute_embedding: bool = True

class UpdateChunkIn(BaseModel):
    text: str | None = None

class SearchRequest(BaseModel):
    query_text: str | None = None
    query_embedding: list[float] | None = None
    k: int = 5
    algo: Literal["auto", "flat"] = "auto"
    metric: Literal["cosine", "l2"] = "cosine"

class SearchHit(BaseModel):
    chunk_id: str
    document_id: str
    library_id: str
    score: float
    text: str
