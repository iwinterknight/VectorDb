# app/api/search_temporal.py
from __future__ import annotations
from typing import Any, Dict

from fastapi import APIRouter, Query
from temporalio.client import Client

from app.temporal.client import start_query_workflow
from app.temporal.config import TEMPORAL_ADDRESS, TEMPORAL_NAMESPACE
from app.temporal.dtos import WFQueryIn

router = APIRouter(prefix="/v1", tags=["search-temporal"])

@router.post("/libraries/{lib_id}/search/temporal")
async def search_temporal(lib_id: str, body: Dict[str, Any], wait: bool = Query(True)):
    """
    Start durable search via Temporal.
    Body mirrors /v1/libraries/{lib_id}/search (SearchRequest).
    Query param ?wait=true/false to wait or return workflow ids.
    """
    payload = WFQueryIn(library_id=lib_id, request=body, request_id=body.get("request_id"))
    out = await start_query_workflow(payload, wait=wait)
    if wait:
        # WFAnswerOut -> dict
        ans = out  # type: ignore[assignment]
        return {"hits": ans.hits, "meta": ans.meta}
    else:
        wf_id, run_id = out  # type: ignore[assignment]
        return {"workflow_id": wf_id, "run_id": run_id}

@router.get("/temporal/{workflow_id}/status")
async def temporal_status(workflow_id: str):
    """
    Query workflow status() – returns stage, filter snapshot, partial_count
    """
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEMPORAL_NAMESPACE)
    handle = client.get_workflow_handle(workflow_id)
    res = await handle.query("status")
    return res

@router.post("/temporal/{workflow_id}/filters")
async def temporal_update_filters(workflow_id: str, body: Dict[str, Any]):
    """
    Signal workflow to update filters BEFORE retrieve starts.
    """
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEMPORAL_NAMESPACE)
    handle = client.get_workflow_handle(workflow_id)
    await handle.signal("update_filters", body)
    return {"status": "accepted"}
