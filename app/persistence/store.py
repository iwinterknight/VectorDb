# app/persistence/store.py
from __future__ import annotations
import json, os
from pathlib import Path
from typing import Any, Optional

class DiskStore:
    """
    Minimal fs-backed store for snapshot + WAL with atomicity & fsync.
    Layout:
      /data/repo.snapshot.json
      /data/repo.wal.jsonl
      /data/repo.meta.json   (optional, not required here)
    """
    def __init__(self, data_dir: str | None = None):
        base = data_dir or os.getenv("DATA_DIR", "./data")
        self.root = Path(base)
        self.root.mkdir(parents=True, exist_ok=True)
        self.snapshot_path = self.root / "repo.snapshot.json"
        self.wal_path = self.root / "repo.wal.jsonl"

    # -------- helpers
    def _fsync_file(self, f) -> None:
        f.flush()
        os.fsync(f.fileno())

    # -------- WAL
    def append_wal(self, entry: dict) -> None:
        """ Append one JSON line and fsync. """
        line = json.dumps(entry, separators=(",", ":"), ensure_ascii=False)
        with open(self.wal_path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
            self._fsync_file(f)

    # -------- snapshot (atomic)
    def write_snapshot(self, image: dict) -> None:
        tmp = self.snapshot_path.with_suffix(".json.tmp")
        data = json.dumps(image, separators=(",", ":"), ensure_ascii=False)
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(data)
            self._fsync_file(f)
        os.replace(tmp, self.snapshot_path)  # atomic on same fs

        # Truncate WAL after successful snapshot
        with open(self.wal_path, "w", encoding="utf-8") as f:
            f.write("")  # empty
            self._fsync_file(f)

    # -------- load
    def load(self) -> dict[str, Any]:
        """Return {'snapshot': dict|None, 'wal': list[dict]}"""
        snap = None
        if self.snapshot_path.exists():
            snap_text = self.snapshot_path.read_text(encoding="utf-8")
            if snap_text.strip():
                snap = json.loads(snap_text)

        wal_entries: list[dict] = []
        if self.wal_path.exists():
            with open(self.wal_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    wal_entries.append(json.loads(line))
        return {"snapshot": snap, "wal": wal_entries}

    # -------- misc
    def stats(self) -> dict:
        def size(p: Path) -> int:
            return p.stat().st_size if p.exists() else 0
        return {
            "snapshot_bytes": size(self.snapshot_path),
            "wal_bytes": size(self.wal_path),
            "snapshot_path": str(self.snapshot_path),
            "wal_path": str(self.wal_path),
        }
