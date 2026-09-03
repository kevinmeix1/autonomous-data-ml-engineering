from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class ObservationEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    kind: str
    name: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    latency_ms: float | None = None
    tokens: int | None = None
    cost_usd: float | None = None
    success: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class ObservabilityStore:
    def __init__(self) -> None:
        self.events: list[ObservationEvent] = []

    def track(self, event: ObservationEvent) -> None:
        self.events.append(event)

    def summary(self) -> dict[str, Any]:
        return {
            "total_events": len(self.events),
            "llm_calls": sum(1 for e in self.events if e.kind == "llm"),
            "tool_calls": sum(1 for e in self.events if e.kind == "tool"),
            "errors": sum(1 for e in self.events if not e.success),
            "total_tokens": sum(e.tokens or 0 for e in self.events),
            "total_cost_usd": sum(e.cost_usd or 0.0 for e in self.events),
            "avg_latency_ms": (
                sum(e.latency_ms or 0.0 for e in self.events) / max(1, len(self.events))
            ),
        }
