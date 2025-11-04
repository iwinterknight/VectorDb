from fastapi.testclient import TestClient

from app.main import create_app


def _setup_library(client: TestClient):
    lib = client.post("/v1/libraries", json={"name": "mutations"}).json()
    doc = client.post(f"/v1/libraries/{lib['id']}/documents", json={"title": "doc"}).json()
    return lib, doc


def test_chunk_update_and_delete_cycle():
    client = TestClient(create_app())
    lib, doc = _setup_library(client)

    chunk = client.post(
        f"/v1/libraries/{lib['id']}/documents/{doc['id']}/chunks",
        json={"text": "initial text", "compute_embedding": True},
    ).json()
    chunk_id = chunk["id"]
    original_embedding = chunk["embedding"]

    updated = client.patch(
        f"/v1/libraries/{lib['id']}/documents/{doc['id']}/chunks/{chunk_id}",
        json={"text": "updated wording"},
    ).json()
    assert updated["text"] == "updated wording"
    assert updated["embedding"] != original_embedding

    resp = client.delete(
        f"/v1/libraries/{lib['id']}/documents/{doc['id']}/chunks/{chunk_id}"
    )
    assert resp.status_code == 204

    not_found = client.get(
        f"/v1/libraries/{lib['id']}/documents/{doc['id']}/chunks/{chunk_id}"
    )
    assert not_found.status_code == 404
