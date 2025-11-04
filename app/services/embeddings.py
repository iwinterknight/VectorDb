from __future__ import annotations
import time
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

class CohereEmbeddingProvider:
    """
    Cohere embeddings via their Python SDK.
    - Batches requests
    - Retries transient errors
    - Normalizes vectors for cosine similarity
    """
    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        input_type: str | None = None,
        truncate: str | None = None,
        normalize: bool = True,
        max_batch: int = 96,          # safe batch size for cohere embed v3
        max_retries: int = 3,
        backoff_s: float = 0.5,
    ):
        self.api_key = api_key or settings.cohere_api_key
        if not self.api_key:
            raise RuntimeError("Cohere API key missing. Set COHERE_API_KEY or settings.cohere_api_key.")
        self.model = model or settings.cohere_model
        self.input_type = input_type or settings.cohere_input_type
        self.truncate = truncate or settings.cohere_truncate
        self.normalize = normalize
        self.max_batch = max_batch
        self.max_retries = max_retries
        self.backoff_s = backoff_s

        # Lazy import so environments without cohere installed still run with stub
        try:
            import cohere  # type: ignore
        except Exception as e:
            raise RuntimeError(
                "Cohere SDK not installed. Run `pip install cohere` in your environment."
            ) from e

        import cohere  # type: ignore
        self._client = cohere.Client(self.api_key)

        # Dimension: cohere v3 English small = 384, large = 1024 (depends on model variant)
        # We’ll discover on first call if needed elsewhere.

    def _embed_batch(self, batch: list[str]) -> list[list[float]]:
        import cohere  # type: ignore
        last_exc: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                resp = self._client.embed(
                    model=self.model,
                    input_type=self.input_type,
                    texts=batch,
                    truncate=self.truncate,
                )
                # v3 returns resp.embeddings as list[list[float]]
                vecs = resp.embeddings  # type: ignore[attr-defined]
                if self.normalize:
                    out: list[list[float]] = []
                    for v in vecs:
                        v_np = np.asarray(v, dtype=np.float32)
                        v_np /= np.linalg.norm(v_np) + 1e-12
                        out.append(v_np.tolist())
                    return out
                return vecs
            except Exception as e:
                last_exc = e
                if attempt < self.max_retries:
                    time.sleep(self.backoff_s * (2 ** attempt))
                    continue
                raise

        # Normally unreachable
        assert False, f"Unreachable; last_exc={last_exc}"

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        out: list[list[float]] = []
        for i in range(0, len(texts), self.max_batch):
            out.extend(self._embed_batch(texts[i : i + self.max_batch]))
        return out