# app/temporal/workflows.py
from __future__ import annotations
from typing import Any, Dict, List, Optional

from temporalio import workflow
from temporalio.common import RetryPolicy

from app.temporal.dtos import WFQueryIn, WFPreprocessed, WFRetrieved, WFAnswerOut
from app.temporal import activities as acts


@workflow.defn
class QueryWorkflow:
    """
    Durable querying:
      run: preprocess -> retrieve -> rerank -> answer
      signal: update_filters
      query: status, preview
    """

    def __init__(self) -> None:
        # Durable in-workflow state (deterministic)
        self._stage: str = "init"
        self._filters: Optional[Dict[str, Any]] = None
        self._partial: Optional[List[Dict[str, Any]]] = None

    # ------------- Queries -------------

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

    # ------------- Signal -------------

    @workflow.signal
    def update_filters(self, new_filters: Dict[str, Any]) -> None:
        # Only meaningful before we kick off retrieve
        if self._stage in ("init", "preprocess"):
            self._filters = new_filters

    # ------------- Workflow run -------------

    @workflow.run
    async def run(self, payload: WFQueryIn) -> WFAnswerOut:
        # Activity retry policy (optional tweak)
        retry = RetryPolicy(
            initial_interval=1.0,
            backoff_coefficient=2.0,
            maximum_interval=10.0,
            maximum_attempts=5,
        )

        # Step 1: preprocess
        self._stage = "preprocess"
        pre = await workflow.execute_activity(
            acts.preprocess,
            payload.request,
            payload.library_id,
            start_to_close_timeout=workflow.timedelta(seconds=30),
            retry_policy=retry,
        )

        assert isinstance(pre, WFPreprocessed)

        # if we received a Signal before retrieve, merge filters
        if self._filters is not None:
            # overwrite request.filters
            req = dict(pre.request)
            req["filters"] = self._filters
            pre = WFPreprocessed(
                library_id=pre.library_id,
                algo=pre.algo,
                metric=pre.metric,
                k=pre.k,
                request=req,
                filters=self._filters,
            )

        # Step 2: retrieve
        self._stage = "retrieve"
        ret = await workflow.execute_activity(
            acts.retrieve,
            pre,
            schedule_to_close_timeout=workflow.timedelta(seconds=60),
            retry_policy=retry,
        )
        assert isinstance(ret, WFRetrieved)
        # store partial for queries
        self._partial = ret.hits

        # Step 3: rerank (optional exact)
        self._stage = "rerank"
        ret2 = await workflow.execute_activity(
            acts.rerank,
            pre,
            ret,
            start_to_close_timeout=workflow.timedelta(seconds=45),
            retry_policy=retry,
        )
        assert isinstance(ret2, WFRetrieved)
        self._partial = ret2.hits

        # Step 4: answer
        self._stage = "answer"
        out = await workflow.execute_activity(
            acts.answer,
            pre,
            ret2,
            start_to_close_timeout=workflow.timedelta(seconds=30),
            retry_policy=retry,
        )
        assert isinstance(out, WFAnswerOut)

        self._stage = "complete"
        return out
