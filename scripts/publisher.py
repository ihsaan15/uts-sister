"""Utility script to publish batches of events for manual testing/demo."""

from __future__ import annotations

import argparse
import asyncio
import os
import time
from datetime import datetime, timezone
from typing import Iterable

import httpx


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Publish demo events to the aggregator")
    parser.add_argument(
        "--base-url",
        default=os.environ.get("BASE_URL", "http://localhost:8080"),
        help="URL dasar layanan aggregator (default: %(default)s)",
    )
    parser.add_argument(
        "--counts",
        type=int,
        nargs="+",
        default=[5, 5000],
        help="Jumlah event yang akan dikirim. Bisa lebih dari satu nilai.",
    )
    parser.add_argument(
        "--duplicates-ratio",
        type=float,
        default=float(os.environ.get("DUPLICATES_RATIO", 0.2)),
        help="Rasio duplikasi (0-1). Default 0.2 = 20%% duplikat.",
    )
    parser.add_argument(
        "--topic",
        default=os.environ.get("PUBLISH_TOPIC", "load-test"),
        help="Nama topik untuk event uji.",
    )
    return parser.parse_args()


async def publish_batch(
    base_url: str,
    count: int,
    duplicates_ratio: float,
    topic: str,
) -> None:
    unique = max(1, int(count * (1 - duplicates_ratio)))
    ids = [f"evt-{i}" for i in range(unique)]
    now = datetime.now(timezone.utc).isoformat()
    events = []
    for idx in range(count):
        event_id = ids[idx % unique]
        events.append(
            {
                "topic": topic,
                "event_id": event_id,
                "timestamp": now,
                "source": "publisher-script",
                "payload": {"seq": idx},
            }
        )

    async with httpx.AsyncClient(timeout=60.0) as client:
        start = time.perf_counter()
        response = await client.post(f"{base_url}/publish", json=events)
        response.raise_for_status()
        duration = time.perf_counter() - start
        body = response.json()
        print(
            f"Sukses kirim {count} event (duplikat ~{duplicates_ratio:.0%}) "
            f"ke {base_url} dalam {duration:.2f}s -> {body}"
        )


async def main() -> None:
    args = _parse_args()
    for count in args.counts:
        await publish_batch(args.base_url, count, args.duplicates_ratio, args.topic)


if __name__ == "__main__":
    asyncio.run(main())