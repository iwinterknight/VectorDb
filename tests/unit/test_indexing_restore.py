from __future__ import annotations

from uuid import uuid4

from app.domain.models import Chunk, ChunkMeta, Document, IndexAlgo, IndexState, Library
from app.repo.memory import InMemoryRepo
from app.services.indexing import IndexingService


def _prepare_repo():
    repo = InMemoryRepo()

    lib = Library(id=uuid4(), name="restore-lib")
    repo.libraries[lib.id] = lib
    repo.by_library_docs[lib.id] = set()

    doc = Document(id=uuid4(), library_id=lib.id, title="Doc")
    repo.documents[doc.id] = doc
    repo.by_library_docs[lib.id].add(doc.id)
    repo.by_document_chunks[doc.id] = set()

    chunk = Chunk(
        id=uuid4(),
        library_id=lib.id,
        document_id=doc.id,
        text="vector search chunk",
        embedding=[0.5, 0.5, 0.5],
        metadata=ChunkMeta(tags=["restore"]),
    )
    repo.chunks[chunk.id] = chunk
    repo.by_document_chunks[doc.id].add(chunk.id)
    doc.chunk_ids.append(chunk.id)
    lib.embedding_dim = 3

    # Record persisted state for both flat and rp indices
    flat_state = IndexState(
        built=True,
        algo=IndexAlgo.flat,
        metric="cosine",
        params={},
        size=1,
    )
    rp_state = IndexState(
        built=True,
        algo=IndexAlgo.rp,
        metric="cosine",
        params={"trees": 2, "leaf_size": 4, "seed": 7},
        size=1,
    )
    lib.index_states = {"flat": flat_state, "rp": rp_state}
    lib.index_state = rp_state

    return repo, lib


def test_restore_all_indices_rebuilds_cached_indexes():
    repo, lib = _prepare_repo()
    service = IndexingService(repo, store=None)

    restored = service.restore_all_indices()

    assert lib.id in restored
    assert restored[lib.id]["flat"] == 1
    assert restored[lib.id]["rp"] == 1
    assert lib.id in service.flat_indices
    assert lib.id in service.rp_indices
    assert service.flat_indices[lib.id].ids, "flat index should contain chunk ids"
    assert service.rp_indices[lib.id]._id_to_vec, "rp forest should have stored vectors"
