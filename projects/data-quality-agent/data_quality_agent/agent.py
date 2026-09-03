from __future__ import annotations

from typing import Any

from agent_sdk.base import BaseAgent
from agent_sdk.state import AgentExecution, Finding
from domain.enums import AgentState, EvidenceKind, IncidentSeverity
from tool_sdk.registry import ToolRegistry


class DataQualityAgent(BaseAgent):
    name = "data_quality"
    description = "Autonomous data quality investigation agent"

    def __init__(self, tools: ToolRegistry, **kwargs: Any) -> None:
        super().__init__(tools, **kwargs)

    def run(self, objective: str, context: dict[str, Any] | None = None) -> AgentExecution:
        context = context or {}
        self.execution = type(self.execution)(agent=self.name, objective=objective)
        table_id = context.get("table_id", "RAW.CLAIM.claims")
        column = context.get("column", "incurred_amount")

        self._set_state(AgentState.OBSERVING, f"Profiling {table_id}")
        profile = self.call_tool("profile_table", {"table_id": table_id})
        if not profile.get("success"):
            self.execution.state = AgentState.FAILED
            return self.finalize({"success": False, "error": profile.get("error")})

        self._set_state(AgentState.INVESTIGATING, "Analyzing historical distribution")
        hist = self.call_tool("get_historical_distribution", {"table_id": table_id, "column": column})
        self.call_tool("get_lineage", {"node_id": table_id})
        upstream = self.call_tool("get_upstream_changes", {"table_id": table_id})

        self._set_state(AgentState.TESTING, "Running statistical tests")
        psi = self.call_tool("compute_psi", {"table_id": table_id, "column": column})
        ks = self.call_tool("compute_ks_test", {"table_id": table_id, "column": column})
        outliers = self.call_tool("detect_outliers", {"table_id": table_id, "column": column})

        stats_evidence: dict[str, Any] = {}
        if psi.get("success"):
            stats_evidence["psi"] = psi["output"]
        if ks.get("success"):
            stats_evidence["ks"] = ks["output"]
        if outliers.get("success"):
            stats_evidence["outliers"] = outliers["output"]

        hypothesis = context.get("hypothesis", f"Distribution drift on {column}")
        test = self.call_tool(
            "hypothesis_test",
            {"hypothesis": hypothesis, "table_id": table_id, "column": column},
        )

        if test.get("success") and test["output"]["supported"]:
            self.add_hypothesis(hypothesis, test["output"]["confidence"], list(stats_evidence.keys()))
            self.add_finding(
                Finding(
                    title=f"DQ issue: {hypothesis}",
                    severity=IncidentSeverity.HIGH,
                    kind=EvidenceKind.STATISTICAL_TEST,
                    explanation=str(test["output"]["evidence"]),
                    suggested_fix="Investigate upstream schema/load changes and add DQ monitors",
                )
            )

        failed_dims = [
            dim
            for dim, sig in profile["output"]["dimensions"].items()
            if not sig.get("passed", True)
        ]
        for dim in failed_dims:
            self.add_finding(
                Finding(
                    title=f"Failed dimension: {dim}",
                    severity=IncidentSeverity.MEDIUM,
                    kind=EvidenceKind.OBSERVED_FACT,
                    explanation=f"Dimension check failed for {table_id}",
                )
            )

        if upstream.get("success") and len(upstream["output"]["recent_changes"]) > 1:
            self.add_finding(
                Finding(
                    title="Recent schema changes detected",
                    severity=IncidentSeverity.MEDIUM,
                    kind=EvidenceKind.OBSERVED_FACT,
                    explanation="; ".join(upstream["output"]["recent_changes"][:2]),
                )
            )

        return self.finalize(
            {
                "success": True,
                "table_id": table_id,
                "column": column,
                "dimensions": profile["output"]["dimensions"],
                "statistical_tests": stats_evidence,
                "hypothesis_result": test.get("output"),
                "failed_dimensions": failed_dims,
            }
        )
