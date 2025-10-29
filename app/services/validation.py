from __future__ import annotations
from uuid import UUID
from app.repo.memory import InMemoryRepo
from app.domain.errors import BadRequestError

def ensure_dim(repo: InMemoryRepo, lib_id: UUID, vec: list[float]) -> int:
    """Ensure and return the library's embedding_dim."""
    lib = repo.libraries[lib_id]
    dim = len(vec)
    if lib.embedding_dim is None:
        lib.embedding_dim = dim
        return dim
    if lib.embedding_dim != dim:
        raise BadRequestError(
            f"Embedding dimension mismatch: expected {lib.embedding_dim}, got {dim}"
        )
    return lib.embedding_dim
