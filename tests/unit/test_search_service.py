from __future__ import annotations

from uuid import uuid4

from app.domain.dtos import FilterSpec, RerankRequest, SearchRequest
from app.domain.models import Chunk, ChunkMeta, Document, Library
from app.repo.indices.flat import FlatIndex
from app.repo.memory import InMemoryRepo
from app.services.search import SearchService


class StubEmbedder:
    def embed(self, texts: list[str]) -> list[list[float]]:
        # Deterministic 2-D vectors
        return [[1.0, 0.0] for _ in texts]


class StubIndexer:
    def __init__(self, flat=None, rp=None):
        self._flat = flat
        self._rp = rp

    def get_available_index(self, lib_id, prefer=None):
        if prefer == "flat" and self._flat is not None:
            return ("flat", self._flat)
        if prefer == "rp" and self._rp is not None:
            return ("rp", self._rp)
        if self._rp is not None:
            return ("rp", self._rp)
        if self._flat is not None:
            return ("flat", self._flat)
        return (None, None)


def _build_repo():
    repo = InMemoryRepo()

    lib = Library(id=uuid4(), name="lib")
    repo.libraries[lib.id] = lib
    repo.by_library_docs[lib.id] = set()

    doc = Document(id=uuid4(), library_id=lib.id, title="doc")
    repo.documents[doc.id] = doc
    repo.by_library_docs[lib.id].add(doc.id)
    repo.by_document_chunks[doc.id] = set()

    chunk1 = Chunk(
        id=uuid4(),
        library_id=lib.id,
        document_id=doc.id,
        text="cluster one text",
        embedding=[0.9, 0.1],
        metadata=ChunkMeta(tags=["ml", "intro"]),
    )
    chunk2 = Chunk(
        id=uuid4(),
        library_id=lib.id,
        document_id=doc.id,
        text="other topic text",
        embedding=[0.1, 0.9],
        metadata=ChunkMeta(tags=["finance"]),
    )

    repo.chunks[chunk1.id] = chunk1
    repo.chunks[chunk2.id] = chunk2
    repo.by_document_chunks[doc.id].update({chunk1.id, chunk2.id})
    doc.chunk_ids.extend([chunk1.id, chunk2.id])
    lib.embedding_dim = 2

    flat = FlatIndex(metric="cosine")
    flat.rebuild(
        [
            (str(chunk1.id), chunk1.embedding),
            (str(chunk2.id), chunk2.embedding),
        ]
    )
    return repo, lib, chunk1, chunk2, flat


def test_search_filters_down_to_matching_chunk():
    repo, lib, chunk1, chunk2, flat = _build_repo()
    svc = SearchService(repo, StubEmbedder(), StubIndexer(flat=flat))

    req = SearchRequest(
        query_embedding=[0.95, 0.05],
        k=5,
        algo="flat",
        metric="cosine",
        filters=FilterSpec(chunk={"metadata.tags": {"any": ["ml"]}}),
    )
    results = svc.search(lib.id, req)

    ids = {r.chunk_id for r in results}
    assert str(chunk1.id) in ids
    assert str(chunk2.id) not in ids


def test_rerank_orders_candidates_by_similarity():
    repo, lib, chunk1, chunk2, flat = _build_repo()
    svc = SearchService(repo, StubEmbedder(), StubIndexer(flat=flat))

    req = RerankRequest(
        query_embedding=[0.9, 0.1],
        candidate_ids=[str(chunk2.id), str(chunk1.id)],
        k=2,
        metric="cosine",
    )
    reranked = svc.rerank(lib.id, req)

    assert len(reranked) == 2
    assert reranked[0].chunk_id == str(chunk1.id)
    assert reranked[1].chunk_id == str(chunk2.id)
