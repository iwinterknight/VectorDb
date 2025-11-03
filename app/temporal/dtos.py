# app/temporal/dtos.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

# Minimal types Temporal will serialize easily

@dataclass
class WFQueryIn:
    library_id: str
    request: Dict[str, Any]  # shape compatible with your /search body
    request_id: Optional[str] = None  # can be used as workflow_id for idempotency

@dataclass
class WFPreprocessed:
    library_id: str
    algo: str
    metric: str
    k: int
    request: Dict[str, Any]        # normalized
    filters: Optional[Dict[str, Any]] = None

@dataclass
class WFRetrieved:
    hits: List[Dict[str, Any]]     # list of SearchHit-like dicts
    cand_count: int
    algo_used: str
    elapsed_ms: int

@dataclass
class WFAnswerOut:
    hits: List[Dict[str, Any]]
    meta: Dict[str, Any]
