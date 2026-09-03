from __future__ import annotations

from typing import Any

from agent_sdk.base import BaseAgent
from agent_sdk.state import AgentExecution, Finding
from domain.enums import ActionRisk, AgentState, EvidenceKind, IncidentSeverity
from tool_sdk.registry import ToolRegistry


class RetrainingAgent(BaseAgent):
    name = "retraining"
    description = "Champion/challenger retraining with safety gates and approval-gated deploy"

    def __init__(self, tools: ToolRegistry, **kwargs: Any) -> None:
        super().__init__(tools, **kwargs)

    def run(self, objective: str, context: dict[str, Any] | None = None) -> AgentExecution:
        context = context or {}
        self.execution = type(self.execution)(agent=self.name, objective=objective)
        model_id = context.get("model_id", "ml.claims_severity_v3")
        promotion_policy = context.get("promotion_policy", "auc_improvement")

        self._set_state(AgentState.OBSERVING, f"Assessing degradation for {model_id}")
        degradation = self.call_tool("assess_degradation", {"model_id": model_id})
        if not degradation.get("success"):
            self.execution.state = AgentState.FAILED
            return self.finalize({"success": False, "error": degradation.get("error")})

        if not degradation["output"]["retraining_recommended"] and not context.get("force_retrain"):
            return self.finalize(
                {
                    "success": True,
                    "retrained": False,
                    "reason": degradation["output"]["reason"],
                }
            )

        self._set_state(AgentState.INVESTIGATING, "Building dataset and training challenger")
        self.call_tool("build_training_dataset", {"model_id": model_id, "lookback_days": 365})
        train = self.call_tool("train_candidate", {"model_id": model_id})
        if not train.get("success"):
            return self.finalize({"success": False, "error": train.get("error")})

        candidate_id = train["output"]["candidate_id"]
        mode = train["output"]["mode"]

        self._set_state(AgentState.TESTING, "Evaluating challenger vs champion")
        eval_res = self.call_tool(
            "evaluate_candidate",
            {"candidate_id": candidate_id, "champion_model_id": model_id},
        )
        compare = self.call_tool(
            "compare_champion_challenger",
            {
                "champion_model_id": model_id,
                "candidate_id": candidate_id,
                "promotion_policy": promotion_policy,
            },
        )
        gates = self.call_tool(
            "check_safety_gates",
            {"candidate_id": candidate_id, "champion_model_id": model_id},
        )

        promote = compare.get("output", {}).get("promote", False)
        all_passed = gates.get("output", {}).get("all_passed", False)

        self.add_finding(
            Finding(
                title="Challenger evaluation complete",
                severity=IncidentSeverity.INFO if promote else IncidentSeverity.MEDIUM,
                kind=EvidenceKind.OBSERVED_FACT,
                explanation=compare.get("output", {}).get("rationale", ""),
                suggested_fix="deploy_model" if promote and all_passed else "keep champion",
            )
        )

        deployed = False
        awaiting_approval = False
        if promote and all_passed:
            self._set_state(AgentState.REMEDIATING, "Proposing deployment (approval required)")
            action = self.propose_action(
                "deploy_model",
                {
                    "candidate_id": candidate_id,
                    "champion_model_id": model_id,
                    "target_stage": "Production",
                },
                ActionRisk.APPROVAL_REQUIRED,
                rationale=f"Promote challenger per {promotion_policy} policy",
            )
            awaiting_approval = True
            self._set_state(AgentState.AWAITING_APPROVAL, "Deploy awaiting human approval")

        monitor = self.call_tool("monitor_post_deploy", {"model_id": model_id, "hours": 24})

        return self.finalize(
            {
                "success": True,
                "retrained": True,
                "mode": mode,
                "candidate_id": candidate_id,
                "promote_recommended": promote,
                "safety_gates_passed": all_passed,
                "evaluation": eval_res.get("output"),
                "comparison": compare.get("output"),
                "deployed": deployed,
                "awaiting_approval": awaiting_approval,
                "post_deploy_healthy": monitor.get("output", {}).get("healthy"),
            }
        )
