# vectordb_client/examples/temporal_async.py
import time
from vectordb_client import ClientConfig, VectorDBClient, TemporalClient, models as M

cfg = ClientConfig(base_url="http://localhost:8000")
cli = VectorDBClient(cfg)
tcli = TemporalClient(cli)

# Reuse or create a small dataset
lib = cli.create_library("temporal-async-lib", "Temporal async demo")
doc = cli.create_document(lib.id, "Data")
cli.create_chunk(lib.id, doc.id, text="Approximate nearest neighbors trade recall for speed.", metadata={"tags": ["ann", "search"]})
cli.create_chunk(lib.id, doc.id, text="Vector databases enable efficient similarity search.", metadata={"tags": ["search"]})
cli.build_index(lib.id, algo="rp", metric="cosine", params={"trees": 1, "leaf_size": 4, "seed": 42})

# Start workflow without waiting
req = M.SearchRequest(query_text="approximate nearest neighbors", k=5, algo="rp", metric="cosine")
resp = tcli.start_query(lib.id, req, wait=False)
print("Started:", resp)

wf_id = resp.workflow_id

# Poll status
for _ in range(10):
    st = tcli.status(wf_id)
    print("Status:", st.model_dump())
    if st.stage == "complete":
        break
    time.sleep(0.5)

# (Optional) Signal filters early on a new run:
# tcli.signal_filters(wf_id, {"chunk": {"metadata.tags": {"any": ["ann"]}}})

# You can also expose a /result endpoint if you want, but in this demo we start a separate sync run
out_sync = tcli.start_query(lib.id, req, wait=True)
print("Result:", out_sync)
