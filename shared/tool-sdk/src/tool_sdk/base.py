from __future__ import annotations

import time
import traceback
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

from domain.enums import ActionRisk

InputT = TypeVar("InputT", bound=BaseModel)
OutputT = TypeVar("OutputT", bound=BaseModel)


class ToolError(Exception):
    def __init__(self, message: str, *, code: str = "TOOL_ERROR", details: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.details = details or {}


class ToolContext(BaseModel):
    execution_id: str
    agent_name: str
    actor: str = "agent"
    approved_actions: list[str] = Field(default_factory=list)
    dry_run: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class ToolResult(BaseModel, Generic[OutputT]):
    tool_name: str
    risk: ActionRisk
    success: bool
    output: OutputT | None = None
    error: str | None = None
    error_code: str | None = None
    started_at: datetime
    ended_at: datetime
    latency_ms: float
    call_id: str
    approval_required: bool = False
    approved: bool | None = None
    logs: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class BaseTool(ABC, Generic[InputT, OutputT]):
    name: str
    description: str
    risk: ActionRisk
    input_model: type[InputT]
    output_model: type[OutputT]

    def __init__(self) -> None:
        if not getattr(self, "name", None):
            raise ValueError("Tool must define name")
        if self.risk == ActionRisk.PROHIBITED:
            raise ValueError(f"Tool {self.name} cannot be registered as PROHIBITED")

    def validate_input(self, raw: dict[str, Any] | InputT) -> InputT:
        if isinstance(raw, self.input_model):
            return raw
        return self.input_model.model_validate(raw)

    def requires_approval(self, context: ToolContext) -> bool:
        if self.risk == ActionRisk.APPROVAL_REQUIRED:
            return self.name not in context.approved_actions
        return False

    @abstractmethod
    def _execute(self, args: InputT, context: ToolContext) -> OutputT:
        raise NotImplementedError

    def run(self, raw_args: dict[str, Any] | InputT, context: ToolContext) -> ToolResult[OutputT]:
        call_id = str(uuid.uuid4())
        started = datetime.now(timezone.utc)
        t0 = time.perf_counter()
        logs: list[str] = [f"tool={self.name} call_id={call_id} risk={self.risk.value}"]

        try:
            args = self.validate_input(raw_args)
            logs.append(f"validated_input keys={list(args.model_dump().keys())}")

            if self.requires_approval(context):
                ended = datetime.now(timezone.utc)
                return ToolResult(
                    tool_name=self.name,
                    risk=self.risk,
                    success=False,
                    output=None,
                    error="Approval required before execution",
                    error_code="APPROVAL_REQUIRED",
                    started_at=started,
                    ended_at=ended,
                    latency_ms=(time.perf_counter() - t0) * 1000,
                    call_id=call_id,
                    approval_required=True,
                    approved=False,
                    logs=logs,
                )

            if context.dry_run and self.risk != ActionRisk.READ_ONLY:
                output = self._dry_run(args, context)
                ended = datetime.now(timezone.utc)
                return ToolResult(
                    tool_name=self.name,
                    risk=self.risk,
                    success=True,
                    output=output,
                    started_at=started,
                    ended_at=ended,
                    latency_ms=(time.perf_counter() - t0) * 1000,
                    call_id=call_id,
                    approval_required=False,
                    approved=True,
                    logs=logs + ["dry_run=true"],
                    metadata={"dry_run": True},
                )

            output = self._execute(args, context)
            ended = datetime.now(timezone.utc)
            logs.append("execution_success")
            return ToolResult(
                tool_name=self.name,
                risk=self.risk,
                success=True,
                output=output,
                started_at=started,
                ended_at=ended,
                latency_ms=(time.perf_counter() - t0) * 1000,
                call_id=call_id,
                approval_required=False,
                approved=True if self.risk == ActionRisk.APPROVAL_REQUIRED else None,
                logs=logs,
            )
        except ToolError as exc:
            ended = datetime.now(timezone.utc)
            logs.append(f"tool_error code={exc.code}")
            return ToolResult(
                tool_name=self.name,
                risk=self.risk,
                success=False,
                error=str(exc),
                error_code=exc.code,
                started_at=started,
                ended_at=ended,
                latency_ms=(time.perf_counter() - t0) * 1000,
                call_id=call_id,
                logs=logs,
                metadata=exc.details,
            )
        except Exception as exc:  # noqa: BLE001 - boundary
            ended = datetime.now(timezone.utc)
            logs.append(traceback.format_exc(limit=3))
            return ToolResult(
                tool_name=self.name,
                risk=self.risk,
                success=False,
                error=str(exc),
                error_code="UNEXPECTED_ERROR",
                started_at=started,
                ended_at=ended,
                latency_ms=(time.perf_counter() - t0) * 1000,
                call_id=call_id,
                logs=logs,
            )

    def _dry_run(self, args: InputT, context: ToolContext) -> OutputT:
        """Default dry-run: subclasses may override."""
        raise ToolError("Dry-run not implemented for this write tool", code="DRY_RUN_UNSUPPORTED")
