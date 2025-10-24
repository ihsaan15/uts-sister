"""Domain models and DTOs for the aggregator service."""
from __future__ import annotations

from datetime import datetime
from typing import Any, List

from pydantic import BaseModel, Field


class Event(BaseModel):
    """Representation of an incoming event."""

    topic: str = Field(..., min_length=1)
    event_id: str = Field(..., min_length=1)
    timestamp: datetime = Field(...)
    source: str = Field(..., min_length=1)
    payload: dict[str, Any]

    class Config:
        json_schema_extra = {
            "example": {
                "topic": "orders",
                "event_id": "evt-123",
                "timestamp": "2025-01-01T00:00:00Z",
                "source": "system-a",
                "payload": {"order_id": "o-1", "amount": 42},
            }
        }


class PublishRequest(BaseModel):
    """Envelope for publish endpoint supporting single or batch events."""

    events: List[Event]

    @classmethod
    def from_payload(cls, data: Any) -> "PublishRequest":
        if isinstance(data, dict):
            return cls(events=[Event(**data)])
        if isinstance(data, list):
            return cls(events=[Event(**item) for item in data])
        raise ValueError("publish payload must be an object or an array of objects")


class Stats(BaseModel):
    """Service statistics model."""

    received: int
    unique_processed: int
    duplicate_dropped: int
    topics: List[str]
    uptime_seconds: float


class StoredEvent(BaseModel):
    """Model representing a processed event stored for retrieval."""

    topic: str
    event_id: str
    timestamp: datetime
    source: str
    payload: Any

    @classmethod
    def from_event(cls, event: Event) -> "StoredEvent":
        return cls(
            topic=event.topic,
            event_id=event.event_id,
            timestamp=event.timestamp,
            source=event.source,
            payload=event.payload,
        )
