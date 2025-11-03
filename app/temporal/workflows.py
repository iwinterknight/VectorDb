# app/temporal/workflows.py
from __future__ import annotations
from typing import Any, Dict, List, Optional
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

# Activity names are referenced by string to avoid importing activity modules
# (which can break Temporal's workflow sandbox when they pull in non-deterministic
# dependencies like HTTP clients).
PREPROCESS_ACTIVITY = "preprocess"
RETRIEVE_ACTIVITY = "retrieve"
RERANK_ACTIVITY = "rerank"
ANSWER_ACTIVITY = "answer"

@workflow.defn
class QueryWorkflow:
    def __init__(self) -> None:
        self._stage: str = "init"
        self._filters: Optional[Dict[str, Any]] = None
        self._partial: Optional[List[Dict[str, Any]]] = None

    @workflow.query
    def status(self) -> Dict[str, Any]:
        return {
            "stage": self._stage,
            "filters": self._filters,
            "partial_count": 0 if not self._partial else len(self._partial),
        }

    @workflow.query
    def preview(self, n: int = 5) -> List[Dict[str, Any]]:
        if not self._partial:
            return []
        return self._partial[: max(0, n)]

    @workflow.signal
    def update_filters(self, new_filters: Dict[str, Any]) -> None:
        if self._stage in ("init", "preprocess"):
            self._filters = new_filters

    @workflow.run
    async def run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        # Expect payload to contain: library_id, request, (optional) request_id
        retry = RetryPolicy(
            initial_interval=timedelta(seconds=1),
            backoff_coefficient=2.0,
            maximum_interval=timedelta(seconds=10),
            maximum_attempts=5,
        )

        # Step 1: preprocess
        self._stage = "preprocess"
        pre: dict = await workflow.execute_activity(
            PREPROCESS_ACTIVITY,
            args=[payload["request"], payload["library_id"]],
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=retry,
        )

        # merge filters if signaled before retrieve
        if self._filters is not None:
            req = dict(pre["request"])
            req["filters"] = self._filters
            pre = {
                **pre,
                "request": req,
                "filters": self._filters,
            }

        # Step 2: retrieve
        self._stage = "retrieve"
        ret: dict = await workflow.execute_activity(
            RETRIEVE_ACTIVITY,
            args=[pre],
            schedule_to_close_timeout=timedelta(seconds=60),
            retry_policy=retry,
        )
        self._partial = ret.get("hits", [])

        # Step 3: rerank
        self._stage = "rerank"
        ret2: dict = await workflow.execute_activity(
            RERANK_ACTIVITY,
            args=[pre, ret],
            start_to_close_timeout=timedelta(seconds=45),
            retry_policy=retry,
        )
        self._partial = ret2.get("hits", [])

        # Step 4: answer
        self._stage = "answer"
        out: dict = await workflow.execute_activity(
            ANSWER_ACTIVITY,
            args=[pre, ret2],
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=retry,
        )

        self._stage = "complete"
        return out
