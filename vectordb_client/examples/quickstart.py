# vectordb_client/examples/quickstart.py
from vectordb_client import ClientConfig, VectorDBClient, TemporalClient, models as M

cfg = ClientConfig(base_url="http://localhost:8000")
cli = VectorDBClient(cfg)
tcli = TemporalClient(cli)

# 1) library
lib = cli.create_library("demo-lib", "SDK quickstart")
print("Library:", lib.id)

# 2) doc + chunks
doc = cli.create_document(lib.id, "Intro")
cli.create_chunk(
    lib.id,
    doc.id,
    text="Approximate nearest neighbors trade recall for speed.",
    metadata={"name": "ann-1", "tags": ["ann", "search"]},
)
cli.create_chunk(
    lib.id,
    doc.id,
    text="Vector databases enable efficient similarity search.",
    metadata={"name": "search-1", "tags": ["vector", "search"]},
)

# 3) build RP index
cli.build_index(lib.id, algo="rp", metric="cosine", params={"trees":1, "leaf_size":4, "seed":42})

# 4) search
hits = cli.search(lib.id, M.SearchRequest(
    query_text="approximate nearest neighbors", k=3, algo="rp",
    metric="cosine", filters={"chunk":{"metadata.tags":{"any":["ann"]}}}
))
print("Hits:", [h.chunk_id for h in hits])

# 5) temporal (sync)
out = tcli.start_query(lib.id, M.SearchRequest(query_text="nearest neighbors", k=3, algo="rp"), wait=True)
print("Temporal:", out)
