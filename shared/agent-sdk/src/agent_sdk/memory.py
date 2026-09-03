from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class MemoryRecord(BaseModel):
    key: str
    kind: str  # execution | incident | knowledge | solution
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    score: float = 0.0


class AgentMemory:
    """Simple in-process memory with retrieval by keyword overlap."""

    def __init__(self) -> None:
        self._records: list[MemoryRecord] = []

    def store(self, key: str, kind: str, content: str, metadata: dict[str, Any] | None = None) -> None:
        self._records.append(
            MemoryRecord(key=key, kind=kind, content=content, metadata=metadata or {})
        )

    def retrieve(self, query: str, *, kind: str | None = None, limit: int = 5) -> list[MemoryRecord]:
        tokens = {t.lower() for t in query.split() if len(t) > 2}
        scored: list[MemoryRecord] = []
        for record in self._records:
            if kind and record.kind != kind:
                continue
            hay = f"{record.key} {record.content}".lower()
            overlap = sum(1 for t in tokens if t in hay)
            if overlap:
                scored.append(record.model_copy(update={"score": float(overlap)}))
        scored.sort(key=lambda r: r.score, reverse=True)
        return scored[:limit]

    def all(self, kind: str | None = None) -> list[MemoryRecord]:
        if kind is None:
            return list(self._records)
        return [r for r in self._records if r.kind == kind]
