"""Persistent deduplication store built on SQLite."""
from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable, Tuple


_SCHEMA = """
CREATE TABLE IF NOT EXISTS dedup (
    topic TEXT NOT NULL,
    event_id TEXT NOT NULL,
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (topic, event_id)
);

CREATE TABLE IF NOT EXISTS processed_events (
    topic TEXT NOT NULL,
    event_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    source TEXT NOT NULL,
    payload TEXT NOT NULL,
    PRIMARY KEY (topic, event_id)
);
"""


class DedupStore:
    """SQLite-backed idempotency tracker."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._initialize()

    def _initialize(self) -> None:
        with self._connect() as conn:
            conn.executescript(_SCHEMA)
            conn.commit()

    @contextmanager
    def _connect(self) -> Iterable[sqlite3.Connection]:
        with self._lock:
            conn = sqlite3.connect(self._db_path, check_same_thread=False)
            try:
                yield conn
            finally:
                conn.close()

    def mark_processed(
        self,
        topic: str,
        event_id: str,
        timestamp: str,
        source: str,
        payload_json: str,
    ) -> bool:
        """Attempt to record an event as processed; return True if new."""
        with self._connect() as conn:
            try:
                conn.execute(
                    "INSERT INTO dedup (topic, event_id) VALUES (?, ?)",
                    (topic, event_id),
                )
                conn.execute(
                    (
                        "INSERT OR REPLACE INTO processed_events "
                        "(topic, event_id, timestamp, source, payload) "
                        "VALUES (?, ?, ?, ?, ?)"
                    ),
                    (topic, event_id, timestamp, source, payload_json),
                )
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                return False

    def load_events(self, topic: str | None = None) -> list[Tuple[str, str, str, str, str]]:
        """Return list of stored events, optionally filtered by topic."""
        query = "SELECT topic, event_id, timestamp, source, payload FROM processed_events"
        params: tuple[str, ...] = ()
        if topic:
            query += " WHERE topic = ?"
            params = (topic,)
        query += " ORDER BY timestamp"
        with self._connect() as conn:
            return conn.execute(query, params).fetchall()

    def stats(self) -> dict[str, int]:
        """Return dedup statistics."""
        with self._connect() as conn:
            received = conn.execute("SELECT COUNT(*) FROM processed_events").fetchone()[0]
            unique_processed = conn.execute("SELECT COUNT(*) FROM dedup").fetchone()[0]
            return {
                "received": received,
                "unique_processed": unique_processed,
            }
