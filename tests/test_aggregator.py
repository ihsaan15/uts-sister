import asyncio
import time
from datetime import datetime, timezone
from typing import Any, Callable, Dict

import httpx
import pytest

from src.config import Settings
from src.main import create_app


async def wait_for_stats(
    client: httpx.AsyncClient,
    predicate: Callable[[Dict[str, Any]], bool],
    timeout: float = 2.0,
    interval: float = 0.05,
) -> Dict[str, Any]:
    deadline = time.monotonic() + timeout
    last_stats: Dict[str, Any] | None = None
    while time.monotonic() < deadline:
        response = await client.get("/stats")
        response.raise_for_status()
        stats = response.json()
        last_stats = stats
        if predicate(stats):
            return stats
        await asyncio.sleep(interval)
    pytest.fail(f"Condition not met before timeout; last stats: {last_stats}")


@pytest.fixture
def settings(tmp_path):
    return Settings(database_path=tmp_path / "dedup.sqlite", worker_count=2)


@pytest.fixture
async def client(settings):
    app = create_app(settings)
    await app.router.startup()
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            yield client
    finally:
        await app.router.shutdown()


@pytest.mark.asyncio
async def test_deduplication(client: httpx.AsyncClient) -> None:
    event = {
        "topic": "orders",
        "event_id": "evt-1",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": "publisher",
        "payload": {"order_id": 1},
    }
    resp1 = await client.post("/publish", json=event)
    assert resp1.status_code == 200
    resp2 = await client.post("/publish", json=event)
    assert resp2.status_code == 200

    stats = await wait_for_stats(
        client,
        lambda data: data["received"] >= 2 and data["duplicate_dropped"] >= 1,
    )
    assert stats["unique_processed"] == 1

    events_resp = await client.get("/events", params={"topic": "orders"})
    events = events_resp.json()
    assert len(events) == 1
    assert events[0]["event_id"] == "evt-1"


@pytest.mark.asyncio
async def test_persistence_across_restart(tmp_path) -> None:
    settings = Settings(database_path=tmp_path / "dedup.sqlite", worker_count=1)

    app1 = create_app(settings)
    await app1.router.startup()
    transport1 = httpx.ASGITransport(app=app1)
    try:
        async with httpx.AsyncClient(transport=transport1, base_url="http://test") as client1:
            event = {
                "topic": "restart",
                "event_id": "evt-100",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "source": "publisher",
                "payload": {"value": 1},
            }
            await client1.post("/publish", json=event)
            await wait_for_stats(client1, lambda data: data["unique_processed"] >= 1)
    finally:
        await app1.router.shutdown()

    app2 = create_app(settings)
    await app2.router.startup()
    transport2 = httpx.ASGITransport(app=app2)
    try:
        async with httpx.AsyncClient(transport=transport2, base_url="http://test") as client2:
            await client2.post("/publish", json=event)
            stats = await wait_for_stats(
                client2,
                lambda data: data["duplicate_dropped"] >= 1 and data["received"] >= 2,
            )
            assert stats["unique_processed"] == 1
    finally:
        await app2.router.shutdown()


@pytest.mark.asyncio
async def test_schema_validation(client: httpx.AsyncClient) -> None:
    invalid_event = {
        "topic": "orders",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": "publisher",
        "payload": {"order_id": 1},
    }
    response = await client.post("/publish", json=invalid_event)
    assert response.status_code == 422

    invalid_timestamp = {
        "topic": "orders",
        "event_id": "evt-bad",
        "timestamp": "not-a-timestamp",
        "source": "publisher",
        "payload": {"order_id": 2},
    }
    response = await client.post("/publish", json=invalid_timestamp)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_event_listing_by_topic(client: httpx.AsyncClient) -> None:
    now = datetime.now(timezone.utc).isoformat()
    events = [
        {
            "topic": "a",
            "event_id": "evt-a1",
            "timestamp": now,
            "source": "pub",
            "payload": {"value": 1},
        },
        {
            "topic": "b",
            "event_id": "evt-b1",
            "timestamp": now,
            "source": "pub",
            "payload": {"value": 2},
        },
    ]
    await client.post("/publish", json=events)
    await wait_for_stats(client, lambda data: data["unique_processed"] >= 2)

    resp_topic_a = await client.get("/events", params={"topic": "a"})
    data_a = resp_topic_a.json()
    assert len(data_a) == 1
    assert data_a[0]["topic"] == "a"

    resp_all = await client.get("/events")
    data_all = resp_all.json()
    assert len(data_all) == 2


@pytest.mark.asyncio
async def test_stress_batch_processing(client: httpx.AsyncClient) -> None:
    total_events = 500
    unique_ids = 200
    events = []
    timestamp = datetime.now(timezone.utc).isoformat()
    for idx in range(total_events):
        events.append(
            {
                "topic": "stress",
                "event_id": f"evt-{idx % unique_ids}",
                "timestamp": timestamp,
                "source": "publisher",
                "payload": {"seq": idx},
            }
        )

    start = time.perf_counter()
    response = await client.post("/publish", json=events)
    duration = time.perf_counter() - start
    assert response.status_code == 200
    assert duration < 2.0

    stats = await wait_for_stats(
        client,
        lambda data: data["unique_processed"] >= unique_ids
        and data["received"] >= total_events
        and data["duplicate_dropped"] >= total_events - unique_ids,
        timeout=5.0,
    )
    assert stats["duplicate_dropped"] >= total_events - unique_ids
