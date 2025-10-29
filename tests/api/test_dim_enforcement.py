from fastapi.testclient import TestClient
from app.main import create_app

def test_embedding_dim_enforced():
    c = TestClient(create_app())
    lib = c.post("/v1/libraries", json={"name":"demo"}).json()
    lib_id = lib["id"]
    doc = c.post(f"/v1/libraries/{lib_id}/documents", json={"title":"t"}).json()
    doc_id = doc["id"]

    # first chunk sets dim implicitly
    c.post(f"/v1/libraries/{lib_id}/documents/{doc_id}/chunks",
           json={"text":"alpha", "compute_embedding": True})

    # simulate wrong-dim query by sending explicit query_embedding of bad length
    bad = [0.0] * 7
    r = c.post(f"/v1/libraries/{lib_id}/search",
               json={"query_embedding": bad, "k": 1})
    assert r.status_code == 400
    body = r.json()
    assert body["error"] == "BadRequest"
    assert "Embedding dimension mismatch" in body["detail"]
