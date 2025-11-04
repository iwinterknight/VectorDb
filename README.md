# VectorDB

Temporal-enabled vector search playground built with FastAPI. The service lets you
manage libraries → documents → chunks, ingest embeddings (stub or Cohere), build
exact/RP indexes, run synchronous searches, and orchestrate more advanced pipelines
with Temporal.

---

## Table of contents

- [Prerequisites](#prerequisites)
- [Project setup](#project-setup)
- [Configuration](#configuration)
- [Running the API](#running-the-api)
- [Docker stack](#docker-stack)
- [REST quickstart](#rest-quickstart)
- [Python SDK quickstart](#python-sdk-quickstart)
- [Indexes](#indexes)
- [Temporal workflows](#temporal-workflows)
- [Bulk data loader](#bulk-data-loader)
- [Tests](#tests)

---

## Prerequisites

- Python 3.12+
- `uvicorn` for local development (installed via requirements)
- Optional: Docker & docker-compose when running Temporal locally (`temporal/docker-compose.yml`)

---

## Project setup

```bash
git clone https://github.com/<you>/VectorDb.git
cd VectorDb
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

If you want Cohere embeddings, install the SDK as well:

```bash
pip install cohere==5.5.3
```

---

## Configuration

All configuration runs through `.env` at the project root. Key settings:

```env
# Embedding provider: stub (deterministic) or cohere (real API)
EMBEDDING_PROVIDER=stub

# When using Cohere
COHERE_API_KEY=...
COHERE_MODEL=embed-english-v3.0
COHERE_INPUT_TYPE=search_query
COHERE_TRUNCATE=END

# Temporal defaults
TEMPORAL_ADDRESS=localhost:7233
TEMPORAL_NAMESPACE=default
```

The app loads `.env` automatically at startup (important for Uvicorn, workers, and tests).

---

## Running the API

```bash
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

The API logs to both stdout and `logs/vectordb.log` (rotating 5 × 5 MB).

---

## Docker stack

Prefer everything in containers? The root `docker-compose.yml` builds the app, runs the
test suite during image creation, and launches the full stack (VectorDB API, Temporal
worker, Temporal server, UI, and Postgres persistence).

```bash
docker compose up --build
```

- Port 8000 → FastAPI service (`/v1/...`).
- Port 7233 → Temporal gRPC endpoint (for SDK clients).
- Port 8233 → Temporal Web UI.

By default the compose file runs with the stub embedding provider, so no external API
keys are required. Override `EMBEDDING_PROVIDER` (and related Cohere settings) in the
compose file or with an `.env` if you need real embeddings.

Named volumes keep repo snapshots/WAL (`vectordb-data`), API logs (`vectordb-logs`),
and Temporal Postgres state (`temporal-pg`). Because the API loads from snapshot + WAL
on startup and Temporal persists to Postgres, the stack survives container restarts and
crashes. Remove `--build` on subsequent launches to reuse the cached image; Docker will
still re-run tests automatically if the build context changes.

To stop the stack while keeping data:

```bash
docker compose down
```

To wipe all persisted state:

```bash
docker compose down --volumes
```

Bulk data loading remains opt-in. You can run the helper inside the API container at any
time (nothing runs automatically at startup):

```bash
docker compose exec api python scripts/load_dummy_chunks.py --base-url http://api:8000 --build-index
```

---

## REST quickstart

Basic workflow with `curl` or REST clients:

```bash
BASE=http://localhost:8000

# Create a library
curl -s $BASE/v1/libraries -X POST -H "Content-Type: application/json" \
  -d '{"name":"demo-lib","description":"quickstart"}'

# Create a document within the library
curl -s $BASE/v1/libraries/{LIB_ID}/documents -X POST \
  -H "Content-Type: application/json" -d '{"title":"intro"}'

# Create chunks (embeddings computed automatically if compute_embedding=true)
curl -s $BASE/v1/libraries/{LIB_ID}/documents/{DOC_ID}/chunks \
  -X POST -H "Content-Type: application/json" \
  -d '{"text": "vector search basics", "compute_embedding": true}'

# Build an index (rp or flat)
curl -s $BASE/v1/libraries/{LIB_ID}/index/build \
  -X POST -H "Content-Type: application/json" \
  -d '{"algo":"rp","metric":"cosine","params":{"trees":8,"leaf_size":32}}'

# Run a query
curl -s $BASE/v1/libraries/{LIB_ID}/search \
  -X POST -H "Content-Type: application/json" \
  -d '{"query_text":"vector search", "k":5, "algo":"rp"}'
```

All endpoints live under `/v1/...`.

---

## Python SDK quickstart

Install the editable SDK and use the helpers under `vectordb_client`:

```bash
pip install --no-build-isolation --no-deps -e .
```

### Standalone session

```python
from vectordb_client import ClientConfig, VectorDBClient, models as M

cfg = ClientConfig(base_url="http://localhost:8000", timeout_s=30, retries=2)
cli = VectorDBClient(cfg)

lib = cli.create_library("sdk-lib", "Managed via Python client")
doc = cli.create_document(lib.id, "Notes")

chunk = cli.create_chunk(
    lib.id,
    doc.id,
    text="Approximate nearest neighbors trade recall for speed.",
    metadata={"tags": ["ann", "search"]},
)

cli.build_index(lib.id, algo="rp", metric="cosine", params={"trees": 4, "leaf_size": 32})

req = M.SearchRequest(query_text="nearest neighbors", k=3, algo="rp", metric="cosine")
hits = cli.search(lib.id, req)
print([h.chunk_id for h in hits])
```

### Temporal helper

To start asynchronous workflows via Temporal:

```python
from vectordb_client import TemporalClient

tcli = TemporalClient(cli)
resp = tcli.start_query(lib.id, req, wait=False)
print(resp.workflow_id)

status = tcli.status(resp.workflow_id)
preview = tcli.preview(resp.workflow_id, n=3)

# synchronous request (wait=True) returns final result
final = tcli.start_query(lib.id, req, wait=True)
```

The SDK also supports bulk chunk creation, rerank, and index inspection.

---

## Indexes

Two index strategies can be active per-library:

- **Flat**: exact search over all embedding vectors (cosine or L2).
- **RP Forest**: approximate nearest neighbor using random projection trees with rerank.

Each library tracks `index_states` so both can be rebuilt after persistence or restart.
Use `/v1/libraries/{lib_id}/index` to inspect the persisted state and `/v1/libraries/{lib_id}/index/live` to check in-memory status.

---

## Temporal workflows

Temporal powers the orchestrated query pipeline (`app/temporal/*`):

1. **Preprocess** – normalize request, run server-side validation, merge signaled filters.
2. **Retrieve** – call REST `/search` to gather candidates.
3. **Rerank** – optional second pass using rp+exact hybrid.
4. **Answer** – assemble metadata/response (for downstream messaging or UI).

Workers listen on `QUERY_TASK_QUEUE`. Start the Temporal stack via `temporal/docker-compose.yml`, set `TEMPORAL_ADDRESS` and `TEMPORAL_NAMESPACE`, then run:

```bash
python -m app.temporal.worker
```

Clients can poll workflow status, preview partial results, or signal filters before retrieve
completes. Temporal keeps the pipeline resilient (retries, signal handling, long-running queries).

---

## Bulk data loader

`scripts/load_dummy_chunks.py` seeds the API with the synthetic dataset in
`data/chunk_clusters.jsonl` (1,000 chunks covering 200 clusters):

1. Make sure the API is running (`uvicorn app.main:app --reload` by default) and the
   Temporal stack is optional for this loader.
2. Activate your virtualenv: `source .venv/bin/activate`.
3. Run the loader. The command below creates or reuses a `clustered-demo` library,
   uploads all chunks, and builds an RP index:

   ```bash
   python scripts/load_dummy_chunks.py --build-index
   ```

   Use `--base-url` if your API is bound to a different host/port, `--data-file` to
   load your own JSONL, or switch to a flat index with `--algo flat`.

You can verify the imported data with `GET /v1/libraries` or the Python SDK
(`cli.list_libraries()`/`cli.list_chunks(...)`).

---

## Tests

Run everything with `pytest` (stub embedder enforced via `tests/conftest.py`):

```bash
pytest
```

- Unit tests cover search filters/rerank and index restoration.
- API tests validate chunk lifecycle, filter behaviour, dimensional enforcement, and index build/search flows.

---

Happy hacking! Use the REST API for simple integration, the Python SDK for scripting,
and Temporal when you need orchestrated search workflows.
