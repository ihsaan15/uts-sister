"""Aggregator service coordinator and worker management."""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Iterable, List, Optional

from .dedup_store import DedupStore
from .models import Event, Stats, StoredEvent


logger = logging.getLogger(__name__)


class AggregatorService:
    """Coordinates event ingestion, deduplication, and retrieval."""

    def __init__(
        self,
        dedup_store: DedupStore,
        worker_count: int = 2,
        queue_maxsize: int = 0,
    ) -> None:
        self._queue: asyncio.Queue[Event] = asyncio.Queue(maxsize=queue_maxsize)
        self._dedup_store = dedup_store
        self._worker_count = max(1, worker_count)
        self._start_time = datetime.now(timezone.utc)
        self._shutdown = asyncio.Event()
        self._workers: list[asyncio.Task[None]] = []
        self._stats_lock = asyncio.Lock()
        existing = self._dedup_store.load_events()
        self._received = len(existing)
        self._unique_processed = len(existing)
        self._duplicate_dropped = 0
        self._topics = {row[0] for row in existing}

    async def start(self) -> None:
        """Start background workers."""
        logger.info("Starting %s aggregator workers", self._worker_count)
        self._shutdown.clear()
        for idx in range(self._worker_count):
            task = asyncio.create_task(self._worker_loop(idx), name=f"worker-{idx}")
            self._workers.append(task)

    async def stop(self) -> None:
        """Stop workers and drain queue."""
        self._shutdown.set()
        for _ in self._workers:
            await self._queue.put(None)  # type: ignore[arg-type]
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()

    async def submit(self, event: Event) -> None:
        """Queue an event for processing and update received count."""
        async with self._stats_lock:
            self._received += 1
        await self._queue.put(event)

    async def submit_batch(self, events: Iterable[Event]) -> None:
        for event in events:
            await self.submit(event)

    async def get_events(self, topic: Optional[str] = None) -> List[StoredEvent]:
        rows = await asyncio.to_thread(self._dedup_store.load_events, topic)
        result: list[StoredEvent] = []
        for topic_val, event_id, timestamp, source, payload in rows:
            payload_data = json.loads(payload)
            result.append(
                StoredEvent(
                    topic=topic_val,
                    event_id=event_id,
                    timestamp=datetime.fromisoformat(timestamp),
                    source=source,
                    payload=payload_data,
                )
            )
        return result

    async def get_stats(self) -> Stats:
        async with self._stats_lock:
            received = self._received
            unique_processed = self._unique_processed
            duplicate_dropped = self._duplicate_dropped
            topics = sorted(self._topics)
        uptime = (datetime.now(timezone.utc) - self._start_time).total_seconds()
        return Stats(
            received=received,
            unique_processed=unique_processed,
            duplicate_dropped=duplicate_dropped,
            topics=topics,
            uptime_seconds=uptime,
        )

    async def _worker_loop(self, worker_id: int) -> None:
        logger.info("Worker %s started", worker_id)
        while True:
            event = await self._queue.get()
            if event is None:
                self._queue.task_done()
                break
            try:
                await self._process_event(event)
            finally:
                self._queue.task_done()
        logger.info("Worker %s stopped", worker_id)

    async def _process_event(self, event: Event) -> None:
        payload_json = json.dumps(event.payload)
        timestamp_str = event.timestamp.isoformat()
        is_new = await asyncio.to_thread(
            self._dedup_store.mark_processed,
            event.topic,
            event.event_id,
            timestamp_str,
            event.source,
            payload_json,
        )
        if is_new:
            async with self._stats_lock:
                self._unique_processed += 1
                self._topics.add(event.topic)
        else:
            async with self._stats_lock:
                self._duplicate_dropped += 1
            logger.info(
                "Duplicate detected for topic=%s event_id=%s", event.topic, event.event_id
            )
