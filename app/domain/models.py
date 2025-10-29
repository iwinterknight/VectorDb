from __future__ import annotations
from pydantic import BaseModel, Field
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import UUID, uuid4
from enum import Enum

UtcNow = lambda: datetime.now(timezone.utc)

class IndexAlgo(str, Enum):
    flat = "flat"
    rp = "rp"

class ChunkMeta(BaseModel):
    created_at: datetime = Field(default_factory=UtcNow)
    name: str | None = None
    tags: list[str] = Field(default_factory=list)
    custom: dict[str, Any] | None = None

class DocumentMeta(BaseModel):
    created_at: datetime = Field(default_factory=UtcNow)
    author: str | None = None
    source_uri: str | None = None
    tags: list[str] = Field(default_factory=list)

class LibraryMeta(BaseModel):
    created_at: datetime = Field(default_factory=UtcNow)
    owner: str | None = None
    topic: str | None = None

class IndexState(BaseModel):
    built: bool = False
    algo: IndexAlgo | None = None
    metric: Literal["cosine", "l2"] = "cosine"
    params: dict[str, Any] = Field(default_factory=dict)
    size: int = 0
    last_built_at: datetime | None = None

class Chunk(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    library_id: UUID
    document_id: UUID
    text: str
    embedding: list[float] | None = None
    metadata: ChunkMeta = Field(default_factory=ChunkMeta)

class Document(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    library_id: UUID
    title: str
    metadata: DocumentMeta = Field(default_factory=DocumentMeta)
    chunk_ids: list[UUID] = Field(default_factory=list)

class Library(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    name: str
    description: str | None = None
    metadata: LibraryMeta = Field(default_factory=LibraryMeta)
    index_state: IndexState = Field(default_factory=IndexState)
    embedding_dim: int | None = None