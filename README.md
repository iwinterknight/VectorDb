# VectorDB (Day 1)

A small Vector DB API in FastAPI with Libraries → Documents → Chunks,
stub embeddings, Flat (exact) search, and per-library embedding dimension enforcement.

## Run (local)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
