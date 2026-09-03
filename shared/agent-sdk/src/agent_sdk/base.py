from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

from agent_sdk.memory import AgentMemory
from agent_sdk.state import (
    AgentExecution,
    EvidenceItem,
    Finding,
    Hypothesis,
    ProposedAction,
    ToolCallRecord,
)
from domain.enums import ActionRisk, AgentState, EvidenceKind
from tool_sdk.base import ToolContext
from tool_sdk.registry import ToolRegistry


class BaseAgent(ABC):
    name: str
    description: str

    def __init__(
        self,
        tools: ToolRegistry,
        memory: AgentMemory | None = None,
        *,
        actor: str = "agent",
    ) -> None:
        self.tools = tools
        self.memory = memory or AgentMemory()
        self.actor = actor
        self.execution = AgentExecution(agent=self.name, objective="")

    def _set_state(self, state: AgentState, detail: str) -> None:
        self.execution.state = state
        self.execution.add_timeline(state.value, detail)

    def call_tool(self, name: str, args: dict[str, Any], *, approved: bool = False) -> dict[str, Any]:
        approved_actions = list(self.execution.metadata.get("approved_actions", []))
        if approved and name not in approved_actions:
            approved_actions.append(name)
        context = ToolContext(
            execution_id=self.execution.execution_id,
            agent_name=self.name,
            actor=self.actor,
            approved_actions=approved_actions,
            dry_run=bool(self.execution.metadata.get("dry_run", False)),
        )
        result = self.tools.call(name, args, context)
        summary = None
        if result.success and result.output is not None:
            dumped = result.output.model_dump(mode="json")
            summary = str(dumped)[:500]
            self.execution.tool_results.append({"tool": name, "output": dumped})
            self.execution.evidence.append(
                EvidenceItem(
                    kind=EvidenceKind.TOOL_RESULT,
                    summary=f"{name} returned structured data",
                    source=name,
                    data={"args": args, "output": dumped},
                )
            )
        self.execution.tool_calls.append(
            ToolCallRecord(
                call_id=result.call_id,
                tool_name=name,
                risk=result.risk,
                args=args,
                success=result.success,
                latency_ms=result.latency_ms,
                error=result.error,
                output_summary=summary,
                started_at=result.started_at,
                ended_at=result.ended_at,
            )
        )
        if result.approval_required:
            action = ProposedAction(
                tool_name=name,
                args=args,
                risk=result.risk,
                rationale=f"Tool {name} requires approval",
                approval_required=True,
                status="proposed",
            )
            self.execution.actions.append(action)
            self._set_state(AgentState.AWAITING_APPROVAL, f"Approval needed for {name}")
        if not result.success and result.error:
            self.execution.errors.append(f"{name}: {result.error}")
        return result.model_dump(mode="json")

    def add_hypothesis(self, statement: str, confidence: float, evidence_ids: list[str] | None = None) -> Hypothesis:
        hyp = Hypothesis(
            statement=statement,
            confidence=confidence,
            supporting_evidence=evidence_ids or [],
        )
        self.execution.hypotheses.append(hyp)
        self.execution.evidence.append(
            EvidenceItem(
                kind=EvidenceKind.AGENT_HYPOTHESIS,
                summary=statement,
                source=self.name,
                data={"hypothesis_id": hyp.hypothesis_id, "confidence": confidence},
                confidence=confidence,
            )
        )
        return hyp

    def add_finding(self, finding: Finding) -> None:
        self.execution.findings.append(finding)

    def propose_action(
        self,
        tool_name: str,
        args: dict[str, Any],
        risk: ActionRisk,
        rationale: str,
    ) -> ProposedAction:
        action = ProposedAction(
            tool_name=tool_name,
            args=args,
            risk=risk,
            rationale=rationale,
            approval_required=risk == ActionRisk.APPROVAL_REQUIRED,
            status="proposed",
        )
        self.execution.actions.append(action)
        self.execution.evidence.append(
            EvidenceItem(
                kind=EvidenceKind.RECOMMENDED_ACTION,
                summary=rationale,
                source=self.name,
                data=action.model_dump(mode="json"),
            )
        )
        return action

    def approve_action(self, action_id: str, approver: str = "human") -> dict[str, Any]:
        for action in self.execution.actions:
            if action.action_id == action_id:
                action.status = "approved"
                approved = list(self.execution.metadata.get("approved_actions", []))
                approved.append(action.tool_name)
                self.execution.metadata["approved_actions"] = approved
                self.execution.approvals.append(
                    {
                        "action_id": action_id,
                        "tool_name": action.tool_name,
                        "approver": approver,
                        "at": datetime.now(timezone.utc).isoformat(),
                        "decision": "approved",
                    }
                )
                result = self.call_tool(action.tool_name, action.args, approved=True)
                action.status = "executed" if result.get("success") else "failed"
                action.result = result
                return result
        raise KeyError(f"Unknown action_id: {action_id}")

    def reject_action(self, action_id: str, approver: str = "human", reason: str = "") -> None:
        for action in self.execution.actions:
            if action.action_id == action_id:
                action.status = "rejected"
                self.execution.approvals.append(
                    {
                        "action_id": action_id,
                        "tool_name": action.tool_name,
                        "approver": approver,
                        "at": datetime.now(timezone.utc).isoformat(),
                        "decision": "rejected",
                        "reason": reason,
                    }
                )
                return
        raise KeyError(f"Unknown action_id: {action_id}")

    @abstractmethod
    def run(self, objective: str, context: dict[str, Any] | None = None) -> AgentExecution:
        raise NotImplementedError

    def finalize(self, result: dict[str, Any]) -> AgentExecution:
        self.execution.final_result = result
        self.execution.end_time = datetime.now(timezone.utc)
        if self.execution.state not in {AgentState.AWAITING_APPROVAL, AgentState.FAILED}:
            self.execution.state = AgentState.COMPLETED
        self.memory.store(
            key=self.execution.execution_id,
            kind="execution",
            content=f"{self.name}: {self.execution.objective} -> {result}",
            metadata={"agent": self.name, "result": result},
        )
        return self.execution
