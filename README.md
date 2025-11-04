# VectorDB

VectorDB is a FastAPI-powered prototype vector database for managing libraries of documents, chunking them into embeddings, and performing similarity search with simple indexing strategies. It ships with an in-memory repository backed by disk snapshots and a write-ahead log so you can experiment with end-to-end retrieval workflows locally.

## Features
- REST API for creating libraries, documents, and text chunks with optional metadata.
- Stub embedding provider (384 dimensions) with hooks to swap in a real embedding service.
- Flat and random-projection (RP) indexes with cosine or L2 distance metrics.
- Vector search and re-ranking endpoints with filter support and temporal search experiments.
- Disk-backed persistence (`./data` by default) using atomic snapshots plus WAL replay on startup.

## Prerequisites
- Python 3.11+
- `pip` (or `uv`/`pipx`) for dependency installation

## Installation
```bash
# clone this repository first, then from the project root:
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Optional environment variables:
- `DATA_DIR` – override the folder where snapshots and WAL files are stored (default: `./data`).
- `EMBEDDING_DIM` – embedding width expected by the system (default: `384`).

## Running the API
Start the service with Uvicorn:
```bash
uvicorn app.main:app --reload --port 8000
```

Swagger UI is available at `http://localhost:8000/docs` and the raw OpenAPI schema at `/openapi.json`.

The server loads any existing snapshot/WAL data on startup and writes new updates as requests arrive. Shut down gracefully to ensure all state is flushed to disk.

## Example workflow
Use `curl` or your preferred HTTP client to walk through the lifecycle of a library.

1. **Create a library**
   ```bash
   curl -X POST http://localhost:8000/v1/libraries \
        -H 'Content-Type: application/json' \
        -d '{"name":"Demo Library","description":"Sample collection"}'
   ```
   Save the returned `id` as `LIB_ID`.

2. **Add a document**
   ```bash
   curl -X POST http://localhost:8000/v1/libraries/$LIB_ID/documents \
        -H 'Content-Type: application/json' \
        -d '{"title":"User Guide"}'
   ```
   Capture the document `id` as `DOC_ID`.

3. **Create chunks**
   ```bash
   curl -X POST http://localhost:8000/v1/libraries/$LIB_ID/documents/$DOC_ID/chunks \
        -H 'Content-Type: application/json' \
        -d '{"text":"Vector databases store embeddings.","metadata":{"section":"intro"},"compute_embedding":true}'
   ```
   Repeat as needed. Set `compute_embedding` to `false` if you intend to provide your own embedding later.

4. **Build an index**
   ```bash
   curl -X POST http://localhost:8000/v1/libraries/$LIB_ID/index/build \
        -H 'Content-Type: application/json' \
        -d '{"algo":"rp","metric":"cosine"}'
   ```
   This stores index metadata to disk so it can be restored on the next startup.

5. **Search**
   ```bash
   curl -X POST http://localhost:8000/v1/libraries/$LIB_ID/search \
        -H 'Content-Type: application/json' \
        -d '{"query_text":"vector database","k":3}'
   ```
   The response returns ranked chunks along with their document and library identifiers. Use `/search/rerank` for re-ranking known chunk IDs or `/search-temporal` routes for experimental time-aware queries.

## Testing
Run the test suite with `pytest`:
```bash
pytest
```

## Next steps
- Swap the stub embedding provider (`app/services/embeddings.py`) with a real model or API.
- Integrate additional ANN algorithms inside `app/services/indexing.py`.
- Extend the filtering grammar in `app/domain/dtos.py` to support richer metadata queries.
