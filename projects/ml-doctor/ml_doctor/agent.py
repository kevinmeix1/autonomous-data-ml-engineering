from __future__ import annotations

from typing import Any

from agent_sdk.base import BaseAgent
from agent_sdk.state import AgentExecution, Finding
from domain.enums import AgentState, EvidenceKind, IncidentSeverity
from tool_sdk.registry import ToolRegistry


class MLDoctorAgent(BaseAgent):
    name = "ml_doctor"
    description = "ML model health monitor — drift, calibration, latency, and incident diagnosis"

    def __init__(self, tools: ToolRegistry, **kwargs: Any) -> None:
        super().__init__(tools, **kwargs)

    def run(self, objective: str, context: dict[str, Any] | None = None) -> AgentExecution:
        context = context or {}
        self.execution = type(self.execution)(agent=self.name, objective=objective)
        model_id = context.get("model_id", "ml.claims_severity_v3")

        self._set_state(AgentState.OBSERVING, f"Loading metrics for {model_id}")
        metrics = self.call_tool("get_model_metrics", {"model_id": model_id})
        if not metrics.get("success"):
            self.execution.state = AgentState.FAILED
            return self.finalize({"success": False, "error": metrics.get("error")})

        self._set_state(AgentState.INVESTIGATING, "Analyzing features, drift, and inference stats")
        self.call_tool("get_feature_distributions", {"model_id": model_id})
        model_features = context.get("features") or ["avg_incurred_12m", "days_to_report", "policy_risk_score"]
        for feat in model_features:
            self.call_tool("detect_drift", {"model_id": model_id, "feature": feat, "method": "both"})

        self.call_tool("get_inference_stats", {"model_id": model_id, "hours": 24})
        pipeline = self.call_tool("get_feature_pipeline_status", {"model_id": model_id})

        self._set_state(AgentState.HYPOTHESIZING, "Running statistical diagnosis")
        diagnosis = self.call_tool(
            "diagnose_incident",
            {"model_id": model_id, "objective": objective},
        )
        if not diagnosis.get("success"):
            return self.finalize({"success": False, "error": diagnosis.get("error")})

        out = diagnosis["output"]
        domain = out["problem_domain"]
        self.add_hypothesis(f"Root cause domain: {domain}", out["confidence"], [])

        self.add_finding(
            Finding(
                title=f"{domain} issue detected",
                severity=IncidentSeverity.HIGH if domain in {"DATA", "INFRASTRUCTURE"} else IncidentSeverity.MEDIUM,
                kind=EvidenceKind.STATISTICAL_TEST,
                explanation=out["summary"],
                suggested_fix=f"See recommend_action for {domain}",
            )
        )

        self._set_state(AgentState.TESTING, "Generating recommendations")
        rec = self.call_tool("recommend_action", {"model_id": model_id, "problem_domain": domain})

        return self.finalize(
            {
                "success": True,
                "model_id": model_id,
                "problem_domain": domain,
                "confidence": out["confidence"],
                "signals": out["signals"],
                "statistical_tests": out["statistical_tests"],
                "pipeline_healthy": pipeline.get("output", {}).get("pipeline_healthy", True),
                "degradation_detected": metrics["output"].get("degradation_detected", False),
                "recommendations": rec.get("output", {}).get("recommended_actions", []),
            }
        )
