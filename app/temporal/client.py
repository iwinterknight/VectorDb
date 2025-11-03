# app/temporal/client.py
from __future__ import annotations
import asyncio
import uuid
from typing import Optional

from temporalio.client import Client
from temporalio.common import WorkflowIDReusePolicy

from app.temporal.config import TEMPORAL_ADDRESS, TEMPORAL_NAMESPACE, QUERY_TASK_QUEUE
from app.temporal.workflows import QueryWorkflow
from app.temporal.dtos import WFQueryIn, WFAnswerOut


async def start_query_workflow(
    payload: WFQueryIn,
    wait: bool = True,
) -> WFAnswerOut | tuple[str, str]:
    """
    Start QueryWorkflow. If wait=True, await result. Else return (workflow_id, run_id).
    """
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEMPORAL_NAMESPACE)

    workflow_id = payload.request_id or f"query-{uuid.uuid4()}"
    handle = await client.start_workflow(
        QueryWorkflow.run,
        payload,
        id=workflow_id,
        task_queue=QUERY_TASK_QUEUE,
        id_reuse_policy=WorkflowIDReusePolicy.ALLOW_DUPLICATE_FAILED_ONLY,
    )

    if wait:
        result = await handle.result()  # WFAnswerOut
        return result
    else:
        return handle.id, handle.first_execution_run_id
