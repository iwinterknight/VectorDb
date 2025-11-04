# vectordb_client/examples/compare_indexes.py
from vectordb_client import ClientConfig, VectorDBClient, models as M

cfg = ClientConfig(base_url="http://localhost:8000")
cli = VectorDBClient(cfg)

lib = cli.create_library("sanity-lib", "Compare flat vs rp")
doc = cli.create_document(lib.id, "ANN vs Flat")

texts = [
    "Approximate nearest neighbors trade recall for speed.",
    "Vector databases enable efficient similarity search over embeddings.",
    "Transformers rely on self-attention mechanisms.",
    "Neural networks learn layered representations of data.",
]
for i, t in enumerate(texts, 1):
    cli.create_chunk(
        lib.id,
        doc.id,
        text=t,
        metadata={"name": f"ex-{i}", "tags": ["ml"] if i != 2 else ["search", "vector"]},
    )

# Build both indexes
cli.build_index(lib.id, algo="flat", metric="cosine")
cli.build_index(lib.id, algo="rp", metric="cosine", params={"trees": 1, "leaf_size": 4, "seed": 42})

q = "approximate nearest neighbors"
req_flat = M.SearchRequest(query_text=q, k=3, algo="flat", metric="cosine")
req_rp   = M.SearchRequest(query_text=q, k=3, algo="rp",   metric="cosine")

hits_flat = cli.search(lib.id, req_flat)
hits_rp   = cli.search(lib.id, req_rp)

print("\nFLAT:")
for h in hits_flat:
    print(h.score, h.text)

print("\nRP:")
for h in hits_rp:
    print(h.score, h.text)
