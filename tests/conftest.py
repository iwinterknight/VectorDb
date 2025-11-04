import os

# Ensure tests always use the stub embedding provider to avoid external calls
os.environ.setdefault("EMBEDDING_PROVIDER", "stub")
