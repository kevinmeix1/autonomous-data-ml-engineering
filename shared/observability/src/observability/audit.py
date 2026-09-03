from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class AuditRecord(BaseModel):
    audit_id: str = Field(default_factory=lambda: str(uuid4()))
    who: str
    what: str
    why: str
    when: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    agent: str | None = None
    tool: str | None = None
    before_state: dict[str, Any] | None = None
    after_state: dict[str, Any] | None = None
    approval: dict[str, Any] | None = None
    result: dict[str, Any] | None = None
    immutable: bool = True


class AuditLog:
    """Append-only audit log (immutable from normal UI)."""

    def __init__(self) -> None:
        self._records: list[AuditRecord] = []

    def append(self, record: AuditRecord) -> AuditRecord:
        self._records.append(record)
        return record

    def list(self, *, limit: int = 200) -> list[AuditRecord]:
        return list(self._records[-limit:])

    def delete(self, audit_id: str) -> None:
        raise PermissionError("Audit log is immutable")
