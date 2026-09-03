from __future__ import annotations

from typing import Any

from agent_sdk.base import BaseAgent
from agent_sdk.state import AgentExecution, Finding
from domain.enums import AgentState, EvidenceKind, FindingSeverity, IncidentSeverity
from tool_sdk.registry import ToolRegistry

_SEVERITY_MAP = {
    FindingSeverity.CRITICAL.value: IncidentSeverity.CRITICAL,
    FindingSeverity.HIGH.value: IncidentSeverity.HIGH,
    FindingSeverity.MEDIUM.value: IncidentSeverity.MEDIUM,
    FindingSeverity.LOW.value: IncidentSeverity.LOW,
    FindingSeverity.SUGGESTION.value: IncidentSeverity.INFO,
}


class DbtReviewAgent(BaseAgent):
    name = "dbt_review"
    description = "Autonomous dbt PR review agent for SQL quality, lineage, and cost"

    def __init__(self, tools: ToolRegistry, **kwargs: Any) -> None:
        super().__init__(tools, **kwargs)

    def run(self, objective: str, context: dict[str, Any] | None = None) -> AgentExecution:
        context = context or {}
        self.execution = type(self.execution)(agent=self.name, objective=objective)
        pr_id = context.get("pr_id", "PR-001")
        model_id = context.get("model_unique_id", "model.analytics.fct_claims")
        structured: list[dict[str, Any]] = []

        self._set_state(AgentState.OBSERVING, f"Inspecting PR {pr_id}")
        pr = self.call_tool(
            "inspect_pr_files",
            {"pr_id": pr_id, "changed_files": context.get("changed_files", [])},
        )
        if not pr.get("success"):
            self.execution.state = AgentState.FAILED
            return self.finalize({"success": False, "error": pr.get("error")})

        target_models = [
            f["model_unique_id"]
            for f in pr["output"]["files"]
            if f.get("model_unique_id")
        ] or [model_id]

        self._set_state(AgentState.INVESTIGATING, "Loading manifest and SQL")
        self.call_tool("get_dbt_manifest", {"model_unique_id": target_models[0]})

        for mid in target_models:
            sql_res = self.call_tool("get_model_sql", {"model_unique_id": mid})
            if not sql_res.get("success"):
                continue

            self._set_state(AgentState.TESTING, f"Running static checks on {mid}")
            static = self.call_tool("run_static_checks", {"model_unique_id": mid})
            if static.get("success"):
                for item in static["output"]["findings"]:
                    structured.append(item)
                    sev = _SEVERITY_MAP.get(item["severity"], IncidentSeverity.MEDIUM)
                    self.add_finding(
                        Finding(
                            title=f"{item['category']}: {item['message']}",
                            severity=sev,
                            kind=EvidenceKind.OBSERVED_FACT,
                            explanation=item["evidence"],
                            file=item.get("file"),
                            line=item.get("line"),
                            suggested_fix=item.get("fix"),
                        )
                    )

            tests = self.call_tool("run_dbt_tests", {"model_unique_id": mid})
            if tests.get("success"):
                for t in tests["output"]["tests"]:
                    if t["status"] == "fail":
                        entry = {
                            "severity": FindingSeverity.HIGH.value,
                            "category": "dbt_test_failure",
                            "message": t.get("message") or t["test_name"],
                            "file": sql_res["output"]["path"],
                            "line": None,
                            "evidence": f"test={t['test_name']} failures={t.get('failures', 0)}",
                            "fix": f"Fix underlying data/SQL causing {t['test_name']}",
                        }
                        structured.append(entry)
                        self.add_finding(
                            Finding(
                                title=f"Failed test: {t['test_name']}",
                                severity=IncidentSeverity.HIGH,
                                kind=EvidenceKind.OBSERVED_FACT,
                                explanation=entry["evidence"],
                                file=entry["file"],
                                suggested_fix=entry["fix"],
                            )
                        )

            self.call_tool("get_lineage", {"model_unique_id": mid})
            self.call_tool("get_query_characteristics", {"model_unique_id": mid, "limit": 5})
            cost = self.call_tool("estimate_cost", {"model_unique_id": mid})
            if cost.get("success") and cost["output"]["estimated_usd"] > 5:
                self.add_hypothesis(
                    f"Model {mid} has elevated Snowflake cost",
                    0.75,
                    [f"estimated_usd={cost['output']['estimated_usd']}"],
                )

        critical = sum(1 for f in structured if f["severity"] == FindingSeverity.CRITICAL.value)
        high = sum(1 for f in structured if f["severity"] == FindingSeverity.HIGH.value)
        approved = critical == 0 and high == 0

        self._set_state(AgentState.DOCUMENTING, "Finalizing PR review")
        return self.finalize(
            {
                "success": True,
                "pr_id": pr_id,
                "models_reviewed": target_models,
                "findings": structured,
                "finding_counts": {
                    "critical": critical,
                    "high": high,
                    "total": len(structured),
                },
                "recommendation": "approve" if approved else "request_changes",
            }
        )
