from fastapi.testclient import TestClient
from app.main import create_app

def test_smoke():
    client = TestClient(create_app())
    lib = client.post("/v1/libraries", json={"name":"demo"}).json()
    lib_id = lib["id"]
    doc = client.post(f"/v1/libraries/{lib_id}/documents", json={"title":"t"}).json()
    doc_id = doc["id"]
    c1 = client.post(f"/v1/libraries/{lib_id}/documents/{doc_id}/chunks",
                     json={"text":"hello embeddings", "compute_embedding": True}).json()
    assert c1["embedding"] is not None
    res = client.post(f"/v1/libraries/{lib_id}/search",
                      json={"query_text":"hello", "k": 1}).json()
    assert len(res) == 1
    assert res[0]["chunk_id"] == c1["id"]
