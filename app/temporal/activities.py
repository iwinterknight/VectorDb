# app/temporal/activities.py
from __future__ import annotations
import time
from typing import Any, Dict, List, Optional
import httpx
from temporalio import activity
from app.temporal.config import APP_BASE_URL

@activity.defn
def preprocess(request: Dict[str, Any], library_id: str) -> Dict[str, Any]:
    algo = request.get("algo", "auto")
    metric = request.get("metric", "cosine")
    k = int(request.get("k", 5))
    k = max(1, min(k, 1000))
    filters = request.get("filters")
    if filters is not None and not isinstance(filters, dict):
        filters = None
    if not request.get("query_text") and not request.get("query_embedding"):
        raise ValueError("Provide query_text or query_embedding")

    normalized = dict(request)
    normalized["algo"] = algo
    normalized["metric"] = metric
    normalized["k"] = k
    if filters is not None:
        normalized["filters"] = filters

    return {
        "library_id": library_id,
        "algo": algo,
        "metric": metric,
        "k": k,
        "request": normalized,
        "filters": filters,
    }

@activity.defn
def retrieve(preprocessed: Dict[str, Any]) -> Dict[str, Any]:
    lib = preprocessed["library_id"]
    url = f"{APP_BASE_URL}/v1/libraries/{lib}/search"
    started = time.perf_counter()
    with httpx.Client(timeout=30.0) as client:
        resp = client.post(url, json=preprocessed["request"])
        resp.raise_for_status()
        hits: List[Dict[str, Any]] = resp.json()
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    return {
        "hits": hits,
        "cand_count": len(hits),
        "algo_used": preprocessed["algo"],
        "elapsed_ms": elapsed_ms,
    }

@activity.defn
def rerank(preprocessed: Dict[str, Any], retrieved: Dict[str, Any]) -> Dict[str, Any]:
    if preprocessed["algo"] != "rp":
        return retrieved
    cand_ids = [h.get("chunk_id") for h in retrieved.get("hits", []) if h.get("chunk_id")]
    if not cand_ids:
        return retrieved

    body: Dict[str, Any] = {
        "candidate_ids": cand_ids,
        "k": preprocessed["k"],
        "metric": preprocessed["metric"],
    }
    req = preprocessed["request"]
    if req.get("query_embedding") is not None:
        body["query_embedding"] = req["query_embedding"]
    else:
        body["query_text"] = req.get("query_text")

    lib = preprocessed["library_id"]
    url = f"{APP_BASE_URL}/v1/libraries/{lib}/search/rerank"
    import time as _t
    started = _t.perf_counter()
    with httpx.Client(timeout=30.0) as client:
        resp = client.post(url, json=body)
        resp.raise_for_status()
        hits2: List[Dict[str, Any]] = resp.json()
    elapsed_ms = int((_t.perf_counter() - started) * 1000)

    return {
        "hits": hits2,
        "cand_count": len(cand_ids),
        "algo_used": "rp+exact",
        "elapsed_ms": retrieved.get("elapsed_ms", 0) + elapsed_ms,
    }

@activity.defn
def answer(preprocessed: Dict[str, Any], final_hits: Dict[str, Any]) -> Dict[str, Any]:
    meta = {
        "algo_initial": preprocessed["algo"],
        "algo_final": final_hits.get("algo_used"),
        "metric": preprocessed["metric"],
        "k": preprocessed["k"],
        "filters_present": preprocessed.get("filters") is not None,
        "elapsed_ms": final_hits.get("elapsed_ms", 0),
        "total_hits": len(final_hits.get("hits", [])),
    }
    return {"hits": final_hits.get("hits", []), "meta": meta}
