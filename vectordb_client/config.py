# vectordb_client/config.py
from __future__ import annotations
from dataclasses import dataclass

DEFAULT_TIMEOUT_S = 20.0
DEFAULT_RETRIES = 2

@dataclass(frozen=True)
class ClientConfig:
    base_url: str                 # url of the app
    api_key: str | None = None    # if auth is added to the sdk client in the future
    timeout_s: float = DEFAULT_TIMEOUT_S
    retries: int = DEFAULT_RETRIES
