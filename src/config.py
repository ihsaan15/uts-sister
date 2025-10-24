"""Application configuration utilities."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _read_int(name: str, default: int) -> int:
    """Read an integer from the environment, falling back to the default."""
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


@dataclass(slots=True)
class Settings:
    """Container for runtime settings with sensible defaults."""

    database_path: Path = Path(os.environ.get("DEDUP_DB_PATH", "data/dedup.sqlite"))
    worker_count: int = _read_int("WORKER_COUNT", 2)
    queue_maxsize: int = _read_int("QUEUE_MAXSIZE", 0)

    def resolved_database_path(self) -> Path:
        """Return an absolute path to the SQLite database file."""
        return self.database_path.expanduser().resolve()
