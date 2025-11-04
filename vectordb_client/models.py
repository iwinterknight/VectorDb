# vectordb_client/models.py
from __future__ import annotations
from typing import Any, Literal, Optional
from pydantic import BaseModel, Field

# -------- Libraries --------
class Library(BaseModel):
    id: str
    name: str
    description: str | None = None
    embedding_dim: int | None = None
    # keep index_state optional to support both legacy/new server shapes
    index_state: dict[str, Any] | None = None
    index_states: dict[str, Any] | None = None

class CreateLibraryIn(BaseModel):
    name: str
    description: str | None = None

class UpdateLibraryIn(BaseModel):
    name: str | None = None
    description: str | None = None

# -------- Documents --------
class Document(BaseModel):
    id: str
    library_id: str
    title: str
    metadata: dict[str, Any] = Field(default_factory=dict)

class CreateDocumentIn(BaseModel):
    title: str

class UpdateDocumentIn(BaseModel):
    title: str | None = None

# -------- Chunks --------
class Chunk(BaseModel):
    id: str
    document_id: str
    library_id: str
    text: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    embedding: list[float] | None = None

class CreateChunkIn(BaseModel):
    text: str
    metadata: dict[str, Any] | None = None
    compute_embedding: bool = True
    embedding: list[float] | None = None   # allow client-supplied vectors

class UpdateChunkIn(BaseModel):
    text: str | None = None
    metadata: dict[str, Any] | None = None
    embedding: list[float] | None = None

# -------- Indexing --------
Algo = Literal["auto", "flat", "rp"]
Metric = Literal["cosine", "l2"]

class IndexBuildRequest(BaseModel):
    algo: Literal["flat", "rp"]
    metric: Metric
    params: dict[str, Any] | None = None

class IndexStateOut(BaseModel):
    built: bool
    algo: str | None = None
    metric: Metric
    params: dict[str, Any] = Field(default_factory=dict)
    size: int = 0
    last_built_at: str | None = None

# -------- Search --------
from pydantic import RootModel

class FilterExpr(RootModel[dict[str, Any]]):
    """Pass-through filter expression."""

class SearchRequest(BaseModel):
    query_text: str | None = None
    query_embedding: list[float] | None = None
    k: int = 5
    algo: Algo = "auto"
    metric: Metric = "cosine"
    filters: dict[str, Any] | None = None

class SearchHit(BaseModel):
    chunk_id: str
    document_id: str
    library_id: str
    score: float
    text: str

class RerankRequest(BaseModel):
    query_text: str | None = None
    query_embedding: list[float] | None = None
    candidate_ids: list[str]
    k: int = 5
    metric: Metric = "cosine"

# -------- Temporal --------
class TemporalStartOut(BaseModel):
    workflow_id: str
    run_id: str | None = None

class TemporalStatusOut(BaseModel):
    stage: str
    filters: dict[str, Any] | None = None
    partial_count: int

class TemporalPreviewOut(RootModel[list[dict[str, Any]]]):
    """Preview hits returned via Temporal query."""

class TemporalResult(BaseModel):
    hits: list[SearchHit]
    meta: dict[str, Any]
