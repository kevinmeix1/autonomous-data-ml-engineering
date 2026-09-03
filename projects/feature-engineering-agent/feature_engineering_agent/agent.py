from __future__ import annotations

from typing import Any

from agent_sdk.base import BaseAgent
from agent_sdk.state import AgentExecution, Finding
from domain.enums import ActionRisk, AgentState, EvidenceKind, IncidentSeverity
from tool_sdk.registry import ToolRegistry


class FeatureEngineeringAgent(BaseAgent):
    name = "feature_engineering"
    description = "Autonomous feature engineering agent with leakage detection"

    def __init__(self, tools: ToolRegistry, **kwargs: Any) -> None:
        super().__init__(tools, **kwargs)

    def run(self, objective: str, context: dict[str, Any] | None = None) -> AgentExecution:
        context = context or {}
        self.execution = type(self.execution)(agent=self.name, objective=objective)
        feature_id = context.get("feature_id", "feat_avg_incurred_12m")
        propose_new = context.get("propose_new", False)

        self._set_state(AgentState.OBSERVING, "Listing feature registry")
        listed = self.call_tool("list_features", {})
        if not listed.get("success"):
            self.execution.state = AgentState.FAILED
            return self.finalize({"success": False, "error": listed.get("error")})

        if propose_new:
            self._set_state(AgentState.INVESTIGATING, "Proposing new feature")
            proposed = self.call_tool(
                "propose_feature",
                {
                    "name": context.get("name", "claim_frequency_90d"),
                    "family": context.get("family", "rolling"),
                    "definition": "Count of claims in trailing 90 days",
                    "source_tables": ["ANALYTICS.CORE.fct_claims"],
                    "transformation": "count(claim_id) over 90d rolling window",
                    "availability_timestamp_column": "as_of_ts",
                },
            )
            if proposed.get("success"):
                feature_id = proposed["output"]["feature_id"]

        self._set_state(AgentState.TESTING, f"Validating feature {feature_id}")
        validation = self.call_tool("validate_feature", {"feature_id": feature_id})
        leakage = self.call_tool(
            "detect_leakage",
            {
                "feature_id": feature_id,
                "outcome_timestamp_column": context.get("outcome_ts", "loss_date"),
                "prediction_timestamp_column": context.get("prediction_ts", "as_of_ts"),
            },
        )
        evaluation = self.call_tool("evaluate_feature", {"feature_id": feature_id})

        if leakage.get("success") and leakage["output"]["leakage_risk"] in {"high", "medium"}:
            self.add_finding(
                Finding(
                    title=f"Leakage risk: {leakage['output']['leakage_risk']}",
                    severity=IncidentSeverity.HIGH
                    if leakage["output"]["leakage_risk"] == "high"
                    else IncidentSeverity.MEDIUM,
                    kind=EvidenceKind.OBSERVED_FACT,
                    explanation="; ".join(leakage["output"]["issues"]) or "Timestamp leakage detected",
                    suggested_fix="Use point-in-time joins and availability_timestamp_column",
                )
            )

        registered = None
        if (
            validation.get("success")
            and validation["output"]["valid"]
            and leakage.get("success")
            and leakage["output"]["leakage_risk"] == "low"
            and evaluation.get("success")
            and evaluation["output"]["recommended"]
        ):
            self._set_state(AgentState.REMEDIATING, "Registering feature")
            registered = self.call_tool(
                "register_feature",
                {"feature_id": feature_id, "version": 1},
            )
        elif evaluation.get("success") and evaluation["output"]["recommended"]:
            self.propose_action(
                "register_feature",
                {"feature_id": feature_id, "version": 1},
                ActionRisk.SAFE_AUTOMATION,
                rationale="Feature passed validation with acceptable leakage risk",
            )

        return self.finalize(
            {
                "success": True,
                "feature_id": feature_id,
                "validation": validation.get("output"),
                "leakage": leakage.get("output"),
                "evaluation": evaluation.get("output"),
                "registered": registered.get("output") if registered else None,
                "feature_count": len(listed["output"]["features"]),
            }
        )
