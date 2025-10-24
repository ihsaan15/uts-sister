"""FastAPI application entrypoint for the event aggregator."""
from __future__ import annotations

import logging
from typing import Any

from fastapi import Body, FastAPI, HTTPException, Query

from .config import Settings
from .dedup_store import DedupStore
from .models import PublishRequest
from .service import AggregatorService

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    dedup_store = DedupStore(settings.resolved_database_path())
    aggregator = AggregatorService(
        dedup_store,
        worker_count=settings.worker_count,
        queue_maxsize=settings.queue_maxsize,
    )

    app = FastAPI(title="Event Aggregator", version="1.0.0")
    app.state.aggregator = aggregator
    app.state.settings = settings

    @app.on_event("startup")
    async def on_startup() -> None:
        await aggregator.start()

    @app.on_event("shutdown")
    async def on_shutdown() -> None:
        await aggregator.stop()

    @app.post("/publish")
    async def publish(payload: Any = Body(...)) -> dict[str, int]:
        try:
            request = PublishRequest.from_payload(payload)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        await aggregator.submit_batch(request.events)
        return {"accepted": len(request.events)}

    @app.get("/events")
    async def list_events(topic: str | None = Query(default=None)) -> list[dict[str, Any]]:
        events = await aggregator.get_events(topic)
        return [event.dict() for event in events]

    @app.get("/stats")
    async def get_stats() -> dict[str, Any]:
        stats = await aggregator.get_stats()
        return stats.dict()

    return app


app = create_app()


def main() -> None:
    import uvicorn

    uvicorn.run("src.main:app", host="0.0.0.0", port=8080, reload=False)


if __name__ == "__main__":
    main()
