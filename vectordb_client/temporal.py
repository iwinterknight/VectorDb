# vectordb_client/temporal.py
from __future__ import annotations
from typing import Any
from .client import VectorDBClient
from . import models as M

class TemporalClient:
    def __init__(self, core: VectorDBClient):
        self.core = core

    def start_query(self, lib_id: str, req: M.SearchRequest, *, wait: bool = True) -> dict | M.TemporalStartOut:
        payload = req.model_dump(exclude_none=True)
        r = self.core._request(
            "POST",
            f"/v1/libraries/{lib_id}/search/temporal?wait={'true' if wait else 'false'}",
            json=payload,
        )
        data = r.json()
        # If wait=true server returns final result shape; else workflow ids
        return data if wait else M.TemporalStartOut(**data)

    def status(self, workflow_id: str) -> M.TemporalStatusOut:
        r = self.core._request("GET", f"/v1/temporal/{workflow_id}/status")
        return M.TemporalStatusOut(**r.json())

    def signal_filters(self, workflow_id: str, filters: dict) -> None:
        self.core._request("POST", f"/v1/temporal/{workflow_id}/filters", json=filters)

    def preview(self, workflow_id: str, n: int = 5) -> list[dict]:
        r = self.core._request("GET", f"/v1/temporal/{workflow_id}/preview?n={n}")
        return r.json()
