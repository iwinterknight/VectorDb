# app/api/admin.py
from __future__ import annotations
from fastapi import APIRouter, Depends
from app.singletons import get_repo, get_store
from app.repo.memory import InMemoryRepo

router = APIRouter(prefix="/v1/admin", tags=["admin"])

def _repo() -> InMemoryRepo: return get_repo()
def _store(): return get_store()

@router.post("/snapshot")
def force_snapshot(repo: InMemoryRepo = Depends(_repo), store = Depends(_store)):
    image = repo.dump_json()
    store.write_snapshot(image)
    return {"status": "ok", "snapshot_bytes": store.stats()["snapshot_bytes"]}

@router.get("/storage")
def storage_stats(store = Depends(_store)):
    return store.stats()
