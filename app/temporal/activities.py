# app/temporal/activities.py
from __future__ import annotations
import time
from typing import Any, Dict, List, Optional

import httpx
from temporalio import activity

from app.temporal.config import (
    APP_BASE_URL,
)
from app.temporal.dtos import WFPreprocessed, WFRetrieved, WFAnswerOut

# ---------- Activity: preprocess ----------

@activity.defn
def preprocess(request: Dict[str, Any], library_id: str) -> WFPreprocessed:
    """
    Normalize/validate fields. No I/O. Deterministic.
    """
    algo = request.get("algo", "auto")
    metric = request.get("metric", "cosine")
    k = int(request.get("k", 5))
    k = max(1, min(k, 1000))  # put some sane bounds

    # normalize filters (ensure dict or None)
    filters = request.get("filters")
    if filters is not None and not isinstance(filters, dict):
        # minimal coercion
        filters = None

    # ensure required fields: either query_text or query_embedding
    if not request.get("query_text") and not request.get("query_embedding"):
        raise ValueError("Provide query_text or query_embedding")

    # build normalized request
    normalized = dict(request)
    normalized["algo"] = algo
    normalized["metric"] = metric
    normalized["k"] = k
    if filters is not None:
        normalized["filters"] = filters

    return WFPreprocessed(
        library_id=library_id,
        algo=algo,
        metric=metric,
        k=k,
        request=normalized,
        filters=filters,
    )

# ---------- Activity: retrieve ----------

@activity.defn
def retrieve(preprocessed: WFPreprocessed) -> WFRetrieved:
    """
    Calls your REST /search endpoint. I/O with retries (temporal will retry activity on failures).
    """
    lib = preprocessed.library_id
    url = f"{APP_BASE_URL}/v1/libraries/{lib}/search"

    started = time.perf_counter()
    with httpx.Client(timeout=30.0) as client:
        resp = client.post(url, json=preprocessed.request)
        resp.raise_for_status()
        hits: List[Dict[str, Any]] = resp.json()

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    return WFRetrieved(
        hits=hits,
        cand_count=len(hits),
        algo_used=preprocessed.algo,
        elapsed_ms=elapsed_ms,
    )

# ---------- Activity: rerank (optional exact) ----------

@activity.defn
def rerank(preprocessed: WFPreprocessed, retrieved: WFRetrieved) -> WFRetrieved:
    """
    Exact re-score ONLY over the candidate ids returned by the first pass.
    If the first pass wasn't rp, pass through unchanged.
    """
    if preprocessed.algo != "rp":
        return retrieved

    # collect candidate ids from the first pass
    cand_ids = [h.get("chunk_id") for h in retrieved.hits if h.get("chunk_id")]
    if not cand_ids:
        return retrieved

    # Build rerank body:
    # Prefer query_embedding if caller provided it; else use query_text.
    body: Dict[str, Any] = {
        "candidate_ids": cand_ids,
        "k": preprocessed.k,
        "metric": preprocessed.metric,
    }
    req = preprocessed.request
    if "query_embedding" in req and req["query_embedding"] is not None:
        body["query_embedding"] = req["query_embedding"]
    else:
        body["query_text"] = req.get("query_text")

    lib = preprocessed.library_id
    url = f"{APP_BASE_URL}/v1/libraries/{lib}/search/rerank"

    started = time.perf_counter()
    with httpx.Client(timeout=30.0) as client:
        resp = client.post(url, json=body)
        resp.raise_for_status()
        hits2: List[Dict[str, Any]] = resp.json()

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    return WFRetrieved(
        hits=hits2,
        cand_count=len(cand_ids),        # original candidate pool size
        algo_used="rp+exact",            # now exact over RP pool
        elapsed_ms=retrieved.elapsed_ms + elapsed_ms,
    )

# ---------- Activity: answer ----------

@activity.defn
def answer(preprocessed: WFPreprocessed, final_hits: WFRetrieved) -> WFAnswerOut:
    """
    Shape the final response. Pure.
    """
    meta = {
        "algo_initial": preprocessed.algo,
        "algo_final": final_hits.algo_used,
        "metric": preprocessed.metric,
        "k": preprocessed.k,
        "filters_present": preprocessed.filters is not None,
        "elapsed_ms": final_hits.elapsed_ms,
        "total_hits": len(final_hits.hits),
    }
    return WFAnswerOut(hits=final_hits.hits, meta=meta)
