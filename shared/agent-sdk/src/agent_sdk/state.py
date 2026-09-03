from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from domain.enums import ActionRisk, AgentState, EvidenceKind, IncidentSeverity


class EvidenceItem(BaseModel):
    evidence_id: str = Field(default_factory=lambda: str(uuid4()))
    kind: EvidenceKind
    summary: str
    source: str
    data: dict[str, Any] = Field(default_factory=dict)
    confidence: float = 1.0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Hypothesis(BaseModel):
    hypothesis_id: str = Field(default_factory=lambda: str(uuid4()))
    statement: str
    confidence: float
    supporting_evidence: list[str] = Field(default_factory=list)
    contradicting_evidence: list[str] = Field(default_factory=list)
    status: str = "open"  # open | supported | rejected | inconclusive
    tests_run: list[str] = Field(default_factory=list)


class Finding(BaseModel):
    finding_id: str = Field(default_factory=lambda: str(uuid4()))
    title: str
    severity: IncidentSeverity
    kind: EvidenceKind
    explanation: str
    evidence_ids: list[str] = Field(default_factory=list)
    file: str | None = None
    line: int | None = None
    suggested_fix: str | None = None


class ProposedAction(BaseModel):
    action_id: str = Field(default_factory=lambda: str(uuid4()))
    tool_name: str
    args: dict[str, Any] = Field(default_factory=dict)
    risk: ActionRisk
    rationale: str
    status: str = "proposed"  # proposed | approved | rejected | executed | failed
    approval_required: bool = False
    result: dict[str, Any] | None = None


class ToolCallRecord(BaseModel):
    call_id: str
    tool_name: str
    risk: ActionRisk
    args: dict[str, Any]
    success: bool
    latency_ms: float
    error: str | None = None
    output_summary: str | None = None
    started_at: datetime
    ended_at: datetime


class AgentExecution(BaseModel):
    execution_id: str = Field(default_factory=lambda: str(uuid4()))
    agent: str
    objective: str
    start_time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    end_time: datetime | None = None
    state: AgentState = AgentState.PENDING
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)
    tool_results: list[dict[str, Any]] = Field(default_factory=list)
    hypotheses: list[Hypothesis] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    actions: list[ProposedAction] = Field(default_factory=list)
    approvals: list[dict[str, Any]] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    timeline: list[dict[str, Any]] = Field(default_factory=list)
    final_result: dict[str, Any] | None = None
    token_usage: dict[str, int] = Field(default_factory=dict)
    cost_usd: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)

    def add_timeline(self, step: str, detail: str, **extra: Any) -> None:
        self.timeline.append(
            {
                "at": datetime.now(timezone.utc).isoformat(),
                "state": self.state.value,
                "step": step,
                "detail": detail,
                **extra,
            }
        )

    def public_view(self) -> dict[str, Any]:
        """Expose investigation artifacts without private chain-of-thought."""
        return {
            "execution_id": self.execution_id,
            "agent": self.agent,
            "objective": self.objective,
            "state": self.state.value,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "investigation_steps": self.timeline,
            "tool_calls": [c.model_dump(mode="json") for c in self.tool_calls],
            "evidence": [e.model_dump(mode="json") for e in self.evidence],
            "hypotheses": [h.model_dump(mode="json") for h in self.hypotheses],
            "findings": [f.model_dump(mode="json") for f in self.findings],
            "actions": [a.model_dump(mode="json") for a in self.actions],
            "approvals": self.approvals,
            "final_result": self.final_result,
            "cost_usd": self.cost_usd,
            "token_usage": self.token_usage,
            "errors": self.errors,
        }
