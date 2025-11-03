# app/temporal/worker.py
from __future__ import annotations
import asyncio

from temporalio.client import Client
from temporalio.worker import Worker

from app.temporal.config import TEMPORAL_ADDRESS, TEMPORAL_NAMESPACE, QUERY_TASK_QUEUE
from app.temporal.workflows import QueryWorkflow
from app.temporal import activities as acts


async def main() -> None:
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEMPORAL_NAMESPACE)

    worker = Worker(
        client,
        task_queue=QUERY_TASK_QUEUE,
        workflows=[QueryWorkflow],
        activities=[acts.preprocess, acts.retrieve, acts.rerank, acts.answer],
    )
    print(f"[worker] listening on task_queue={QUERY_TASK_QUEUE}")
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
