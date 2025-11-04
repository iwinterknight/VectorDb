from fastapi.testclient import TestClient

from app.main import create_app


def test_delete_library_cascades_documents():
    client = TestClient(create_app())

    lib = client.post("/v1/libraries", json={"name": "to-delete"}).json()
    lib_id = lib["id"]
    doc = client.post(f"/v1/libraries/{lib_id}/documents", json={"title": "doc"}).json()
    doc_id = doc["id"]
    chunk = client.post(
        f"/v1/libraries/{lib_id}/documents/{doc_id}/chunks",
        json={"text": "some text", "compute_embedding": True},
    ).json()
    chunk_id = chunk["id"]

    resp = client.delete(f"/v1/libraries/{lib_id}")
    assert resp.status_code == 204

    lib_missing = client.get(f"/v1/libraries/{lib_id}")
    assert lib_missing.status_code == 404

    doc_missing = client.get(f"/v1/libraries/{lib_id}/documents/{doc_id}")
    assert doc_missing.status_code == 404

    chunk_missing = client.get(
        f"/v1/libraries/{lib_id}/documents/{doc_id}/chunks/{chunk_id}"
    )
    assert chunk_missing.status_code == 404
