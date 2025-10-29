from __future__ import annotations
import numpy as np
from typing import Protocol
from app.config import settings

class EmbeddingProvider(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...

class StubEmbeddingProvider:
    """Deterministic pseudo-embeddings for tests/dev."""
    def __init__(self, dim: int | None = None, seed: int = 13):
        self.dim = dim or settings.embedding_dim
        self.rng = np.random.default_rng(seed)

    def embed(self, texts: list[str]) -> list[list[float]]:
        vecs = []
        for t in texts:
            # hash -> seed per text for determinism
            h = abs(hash(t)) % (2**32 - 1)
            rng = np.random.default_rng(h)
            v = rng.normal(size=self.dim).astype(np.float32)
            # L2 normalize for cosine
            v /= np.linalg.norm(v) + 1e-12
            vecs.append(v.tolist())
        return vecs
