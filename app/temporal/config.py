# app/temporal/config.py
from __future__ import annotations
import os

# Temporal connection
TEMPORAL_ADDRESS = os.getenv("TEMPORAL_ADDRESS", "localhost:7233")
TEMPORAL_NAMESPACE = os.getenv("TEMPORAL_NAMESPACE", "default")
QUERY_TASK_QUEUE = os.getenv("QUERY_TASK_QUEUE", "query-tq")

# How activities reach your API (the same FastAPI you run)
# e.g. http://localhost:8000 or http://app:8000 in docker-compose
APP_BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:8000")

# Timeouts (seconds)
ACTIVITY_SCHEDULE_TO_CLOSE = int(os.getenv("ACTIVITY_SCHEDULE_TO_CLOSE", "60"))
ACTIVITY_START_TO_CLOSE = int(os.getenv("ACTIVITY_START_TO_CLOSE", "45"))
WORKFLOW_RUN_TIMEOUT = int(os.getenv("WORKFLOW_RUN_TIMEOUT", "300"))
