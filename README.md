# VectorDB

VectorDB is a FastAPI service that demonstrates the core building blocks of a vector search engine: document ingestion, chunk
embedding, index construction, and similarity queries with lightweight persistence. Use it to prototype retrieval workflows or
as a foundation for plugging in a production-grade embedding provider and ANN index.

## Highlights
- **REST-first**: Create libraries, ingest documents, manage chunks, and trigger searches through JSON APIs.
- **Configurable embeddings**: Ships with a stub 384-dimension embedder that you can replace with any external service.
- **Multiple indexes**: Supports flat and random-projection indexes with cosine or L2 distance metrics.
- **Durable state**: Persists to disk via snapshots and a write-ahead log so the service can be restarted without losing data.
- **Temporal experiments**: Includes experimental endpoints for time-aware retrieval and re-ranking.

## Prerequisites
- Python 3.11+
- `pip` (or an alternative such as `uv` or `pipx`)
- (Optional) Docker and Docker Compose for container-based runs

## Installation
Clone the repository, create a virtual environment, and install the dependencies:

```bash
git clone https://github.com/<your-org>/VectorDb.git
cd VectorDb
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### Configuration
VectorDB reads several environment variables at startup:

| Variable | Description | Default |
| --- | --- | --- |
| `DATA_DIR` | Directory for snapshots and WAL files | `./data` |
| `EMBEDDING_DIM` | Expected dimensionality of vectors | `384` |
| `LOG_LEVEL` | Uvicorn log level | `info` |

Create a `.env` file or export variables before running the server to override defaults.

## Running VectorDB

### Local development server
Launch the FastAPI app with Uvicorn:

```bash
uvicorn app.main:app --reload --port 8000
```

Swagger UI becomes available at `http://localhost:8000/docs`, while the raw OpenAPI schema is served at
`http://localhost:8000/openapi.json`.

### Docker Compose
Alternatively, run the service and its dependencies in containers:

```bash
docker compose up --build
```

The API will be exposed on port `8000` by default. Data persists in the `data/` volume inside the project directory.

## Using the API
The workflow below walks through library creation, ingestion, indexing, and search using `curl`. Swap out curl for any HTTP
client as needed.

1. **Create a library**
   ```bash
   curl -s -X POST http://localhost:8000/v1/libraries \
        -H 'Content-Type: application/json' \
        -d '{"name":"Demo Library","description":"Sample collection"}' | jq
   ```
   Store the returned `id` as `LIB_ID`.

2. **Add a document**
   ```bash
   curl -s -X POST http://localhost:8000/v1/libraries/$LIB_ID/documents \
        -H 'Content-Type: application/json' \
        -d '{"title":"User Guide"}' | jq
   ```
   Save the `id` as `DOC_ID`.

3. **Create chunks**
   ```bash
   curl -s -X POST http://localhost:8000/v1/libraries/$LIB_ID/documents/$DOC_ID/chunks \
        -H 'Content-Type: application/json' \
        -d '{"text":"Vector databases store embeddings.","metadata":{"section":"intro"},"compute_embedding":true}' | jq
   ```
   Add more chunks as required. Set `compute_embedding` to `false` to supply your own vector later via the
   `/chunks/{chunk_id}/embedding` endpoint.

4. **Build an index**
   ```bash
   curl -s -X POST http://localhost:8000/v1/libraries/$LIB_ID/index/build \
        -H 'Content-Type: application/json' \
        -d '{"algo":"rp","metric":"cosine"}' | jq
   ```
   Index metadata is persisted, enabling fast warm starts when the service restarts.

5. **Search the library**
   ```bash
   curl -s -X POST http://localhost:8000/v1/libraries/$LIB_ID/search \
        -H 'Content-Type: application/json' \
        -d '{"query_text":"vector database","k":3}' | jq
   ```
   Responses include ranked chunks, similarity scores, and related document/library IDs. Try `/search/rerank` to re-score known
   chunk IDs or `/search-temporal` for time-aware experiments.

## Testing
Execute the automated tests with `pytest`:

```bash
pytest
```

## Next steps
- Replace the stub embedder in `app/services/embeddings.py` with a hosted model such as OpenAI or Cohere.
- Add additional ANN strategies (e.g., HNSW, IVF) in `app/services/indexing.py`.
- Extend DTOs and filters in `app/domain/dtos.py` to support richer metadata queries and hybrid search.
