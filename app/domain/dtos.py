from pydantic import BaseModel, Field
from typing import Any, Literal
from datetime import datetime

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

class FilterSpec(BaseModel):
    # Simple, flexible filter grammar (subset implemented in filters.py)
    # Example:
    # {
    #   "chunk": {"tags": {"any": ["ml", "ai"]}, "name": {"contains": "intro"}},
    #   "document": {"author": {"eq": "alice"}},
    #   "library": {"topic": {"in": ["nlp", "search"]}}
    # }
    chunk: dict[str, Any] | None = None
    document: dict[str, Any] | None = None
    library: dict[str, Any] | None = None

class SearchRequest(BaseModel):
    query_text: str | None = None
    query_embedding: list[float] | None = None
    k: int = 5
    algo: Literal["auto", "flat", "rp"] = "auto"
    metric: Literal["cosine", "l2"] = "cosine"
    filters: FilterSpec | None = None

class SearchHit(BaseModel):
    chunk_id: str
    document_id: str
    library_id: str
    score: float
    text: str

class IndexBuildRequest(BaseModel):
    algo: Literal["flat", "rp"] = "rp"
    metric: Literal["cosine", "l2"] = "cosine"
    params: dict[str, Any] = Field(default_factory=dict)

class IndexStateOut(BaseModel):
    built: bool
    algo: str | None
    metric: Literal["cosine", "l2"]
    params: dict[str, Any]
    size: int
    last_built_at: datetime | None