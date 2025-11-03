# app/temporal/worker.py
from __future__ import annotations
import asyncio
import os
from concurrent.futures import ThreadPoolExecutor

from temporalio.client import Client
from temporalio.worker import Worker

from app.temporal.config import TEMPORAL_ADDRESS, TEMPORAL_NAMESPACE, QUERY_TASK_QUEUE
from app.temporal.workflows import QueryWorkflow
from app.temporal import activities as acts


async def main() -> None:
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEMPORAL_NAMESPACE)

    # Provide an executor for sync activities
    max_workers = int(os.getenv("TEMPORAL_ACTIVITY_WORKERS", "8"))
    activity_executor = ThreadPoolExecutor(max_workers=max_workers)

    worker = Worker(
        client,
        task_queue=QUERY_TASK_QUEUE,
        workflows=[QueryWorkflow],
        activities=[acts.preprocess, acts.retrieve, acts.rerank, acts.answer],
        activity_executor=activity_executor
    )
    print(f"[worker] listening on task_queue={QUERY_TASK_QUEUE} with {max_workers} activity threads")
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
