# vectordb_client/client.py
from __future__ import annotations
from typing import Any, Iterable
import time
import httpx

from .config import ClientConfig
from .exceptions import (
    VectorDBError, NotFound, Conflict, BadRequest, TransportError, ServerError
)
from . import models as M


class VectorDBClient:
    def __init__(self, config: ClientConfig):
        self.cfg = config
        self._client = httpx.Client(base_url=config.base_url, timeout=config.timeout_s)

    # ------------ low-level helpers ------------
    def _request(self, method: str, url: str, json: Any | None = None) -> httpx.Response:
        tries = max(1, self.cfg.retries + 1)
        last_exc: Exception | None = None
        for attempt in range(tries):
            try:
                resp = self._client.request(method, url, json=json)
                # Map common HTTP errors
                if resp.status_code >= 500:
                    raise ServerError(f"HTTP {resp.status_code}: {resp.text}")
                if resp.status_code == 404:
                    raise NotFound(resp.text)
                if resp.status_code == 409:
                    raise Conflict(resp.text)
                if resp.status_code == 400:
                    raise BadRequest(resp.text)
                if resp.status_code == 422:
                    raise BadRequest(resp.text)
                resp.raise_for_status()
                return resp
            except (httpx.ConnectError, httpx.ReadTimeout, httpx.RemoteProtocolError) as e:
                last_exc = e
                if attempt < tries - 1:
                    time.sleep(0.25 * (2 ** attempt))
                    continue
                raise TransportError(str(e)) from e
            except ServerError:
                if attempt < tries - 1:
                    time.sleep(0.5 * (2 ** attempt))
                    continue
                raise
        assert False, f"unreachable: {last_exc}"

    # ------------ Libraries ------------
    def create_library(self, name: str, description: str | None = None) -> M.Library:
        body = M.CreateLibraryIn(name=name, description=description).model_dump()
        r = self._request("POST", "/v1/libraries", json=body)
        return M.Library(**r.json())

    def list_libraries(self) -> list[M.Library]:
        r = self._request("GET", "/v1/libraries")
        return [M.Library(**x) for x in r.json()]

    def get_library(self, lib_id: str) -> M.Library:
        r = self._request("GET", f"/v1/libraries/{lib_id}")
        return M.Library(**r.json())

    def update_library(self, lib_id: str, *, name: str | None = None, description: str | None = None) -> M.Library:
        body = M.UpdateLibraryIn(name=name, description=description).model_dump(exclude_none=True)
        r = self._request("PATCH", f"/v1/libraries/{lib_id}", json=body)
        return M.Library(**r.json())

    def delete_library(self, lib_id: str) -> None:
        self._request("DELETE", f"/v1/libraries/{lib_id}")

    # ------------ Documents ------------
    def create_document(self, lib_id: str, title: str) -> M.Document:
        r = self._request("POST", f"/v1/libraries/{lib_id}/documents", json=M.CreateDocumentIn(title=title).model_dump())
        return M.Document(**r.json())

    def list_documents(self, lib_id: str) -> list[M.Document]:
        r = self._request("GET", f"/v1/libraries/{lib_id}/documents")
        return [M.Document(**x) for x in r.json()]

    def get_document(self, lib_id: str, doc_id: str) -> M.Document:
        r = self._request("GET", f"/v1/libraries/{lib_id}/documents/{doc_id}")
        return M.Document(**r.json())

    def update_document(self, lib_id: str, doc_id: str, *, title: str | None = None) -> M.Document:
        r = self._request(
            "PATCH",
            f"/v1/libraries/{lib_id}/documents/{doc_id}",
            json=M.UpdateDocumentIn(title=title).model_dump(exclude_none=True),
        )
        return M.Document(**r.json())

    def delete_document(self, lib_id: str, doc_id: str) -> None:
        self._request("DELETE", f"/v1/libraries/{lib_id}/documents/{doc_id}")

    # ------------ Chunks ------------
    def create_chunk(
        self,
        lib_id: str,
        doc_id: str,
        *,
        text: str,
        metadata: dict[str, Any] | None = None,
        compute_embedding: bool = True,
        embedding: list[float] | None = None,
    ) -> M.Chunk:
        body = M.CreateChunkIn(
            text=text,
            metadata=metadata,
            compute_embedding=compute_embedding,
            embedding=embedding,
        ).model_dump(exclude_none=True)
        r = self._request(
            "POST",
            f"/v1/libraries/{lib_id}/documents/{doc_id}/chunks",
            json=body,
        )
        return M.Chunk(**r.json())

    def bulk_create_chunks(
        self,
        lib_id: str,
        doc_id: str,
        items: Iterable[M.CreateChunkIn],
    ) -> list[M.Chunk]:
        body = [it.model_dump(exclude_none=True) for it in items]
        r = self._request(
            "POST",
            f"/v1/libraries/{lib_id}/documents/{doc_id}/chunks:batch",
            json=body,
        )
        return [M.Chunk(**x) for x in r.json()]

    def list_chunks(self, lib_id: str, doc_id: str) -> list[M.Chunk]:
        r = self._request(
            "GET",
            f"/v1/libraries/{lib_id}/documents/{doc_id}/chunks",
        )
        return [M.Chunk(**x) for x in r.json()]

    def update_chunk(
        self,
        lib_id: str,
        doc_id: str,
        chunk_id: str,
        *,
        text: str | None = None,
        metadata: dict[str, Any] | None = None,
        embedding: list[float] | None = None,
    ) -> M.Chunk:
        body = M.UpdateChunkIn(
            text=text,
            metadata=metadata,
            embedding=embedding,
        ).model_dump(exclude_none=True)
        r = self._request(
            "PATCH",
            f"/v1/libraries/{lib_id}/documents/{doc_id}/chunks/{chunk_id}",
            json=body,
        )
        return M.Chunk(**r.json())

    def delete_chunk(self, lib_id: str, doc_id: str, chunk_id: str) -> None:
        self._request(
            "DELETE",
            f"/v1/libraries/{lib_id}/documents/{doc_id}/chunks/{chunk_id}",
        )

    # ------------ Indexing ------------
    def build_index(self, lib_id: str, *, algo: M.IndexBuildRequest.__annotations__['algo'], metric: M.Metric, params: dict[str, Any] | None = None) -> dict:
        body = M.IndexBuildRequest(algo=algo, metric=metric, params=params).model_dump(exclude_none=True)
        r = self._request("POST", f"/v1/libraries/{lib_id}/index/build", json=body)
        return r.json()

    def get_index_state(self, lib_id: str) -> M.IndexStateOut:
        r = self._request("GET", f"/v1/libraries/{lib_id}/index")
        return M.IndexStateOut(**r.json())

    def get_live_index(self, lib_id: str) -> dict:
        r = self._request("GET", f"/v1/libraries/{lib_id}/index/live")
        return r.json()

    # ------------ Search ------------
    def search(self, lib_id: str, req: M.SearchRequest) -> list[M.SearchHit]:
        r = self._request("POST", f"/v1/libraries/{lib_id}/search", json=req.model_dump(exclude_none=True))
        return [M.SearchHit(**x) for x in r.json()]

    def rerank(self, lib_id: str, req: M.RerankRequest) -> list[M.SearchHit]:
        r = self._request("POST", f"/v1/libraries/{lib_id}/search/rerank", json=req.model_dump(exclude_none=True))
        return [M.SearchHit(**x) for x in r.json()]
