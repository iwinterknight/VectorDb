from fastapi.testclient import TestClient
from app.main import create_app

def test_build_rp_and_search():
    c = TestClient(create_app())

    lib = c.post("/v1/libraries", json={"name":"demo"}).json()
    lib_id = lib["id"]
    doc = c.post(f"/v1/libraries/{lib_id}/documents", json={"title":"t"}).json()
    doc_id = doc["id"]

    texts = [
        "neural networks learn representations",
        "vector search with random projections",
        "transformers are attention based",
        "approximate nearest neighbors are fast"
    ]
    for t in texts:
        r = c.post(f"/v1/libraries/{lib_id}/documents/{doc_id}/chunks",
                   json={"text": t, "compute_embedding": True})
        assert r.status_code == 201

    # Build RP index
    r = c.post(f"/v1/libraries/{lib_id}/index/build",
               json={"algo":"rp","metric":"cosine","params":{"trees":6,"leaf_size":16}})
    assert r.status_code == 202
    state = c.get(f"/v1/libraries/{lib_id}/index").json()
    assert state["built"] is True
    assert state["algo"] == "rp"

    # Search using rp explicitly
    res = c.post(f"/v1/libraries/{lib_id}/search",
                 json={"query_text":"approximate neighbors", "k":2, "algo":"rp"}).json()
    assert len(res) >= 1
