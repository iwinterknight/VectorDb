from fastapi.testclient import TestClient
from app.main import create_app

def test_search_with_filters():
    c = TestClient(create_app())

    lib = c.post("/v1/libraries", json={"name":"demo", "description":"play"}).json()
    lib_id = lib["id"]
    doc = c.post(f"/v1/libraries/{lib_id}/documents", json={"title":"notes"}).json()
    doc_id = doc["id"]

    c1 = c.post(f"/v1/libraries/{lib_id}/documents/{doc_id}/chunks",
                json={"text":"ml intro", "metadata":{"tags":["ml","intro"]}, "compute_embedding": True}).json()
    c2 = c.post(f"/v1/libraries/{lib_id}/documents/{doc_id}/chunks",
                json={"text":"finance article", "metadata":{"tags":["finance"]}, "compute_embedding": True}).json()

    # Build flat (optional; search auto would lazy build)
    c.post(f"/v1/libraries/{lib_id}/index/build",
           json={"algo":"flat","metric":"cosine","params":{}})

    res = c.post(f"/v1/libraries/{lib_id}/search",
                 json={"query_text":"ml", "k":5,
                       "filters":{"chunk":{"metadata.tags":{"any":["ml"]}}}}).json()
    ids = {h["chunk_id"] for h in res}
    assert c1["id"] in ids
    assert c2["id"] not in ids
