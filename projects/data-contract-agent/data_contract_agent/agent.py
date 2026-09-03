from __future__ import annotations

from typing import Any

from agent_sdk.base import BaseAgent
from agent_sdk.state import AgentExecution, Finding
from domain.enums import ActionRisk, AgentState, EvidenceKind, IncidentSeverity
from tool_sdk.registry import ToolRegistry


class DataContractAgent(BaseAgent):
    name = "data_contract"
    description = "Data contract guardian for schema change impact analysis"

    def __init__(self, tools: ToolRegistry, **kwargs: Any) -> None:
        super().__init__(tools, **kwargs)

    def run(self, objective: str, context: dict[str, Any] | None = None) -> AgentExecution:
        context = context or {}
        self.execution = type(self.execution)(agent=self.name, objective=objective)
        table_id = context.get("table_id", "RAW.CLAIM.claims")

        self._set_state(AgentState.OBSERVING, "Loading contracts and schema registry")
        contracts = self.call_tool("list_contracts", {"dataset": table_id})
        registry = self.call_tool("get_schema_registry", {"table_id": table_id})
        if not registry.get("success"):
            self.execution.state = AgentState.FAILED
            return self.finalize({"success": False, "error": registry.get("error")})

        self._set_state(AgentState.INVESTIGATING, "Analyzing schema change")
        change = self.call_tool("analyze_schema_change", {"table_id": table_id})
        lineage = self.call_tool("lineage_impact", {"node_id": table_id})
        consumers = self.call_tool("consumer_impact", {"table_id": table_id})

        changes = change.get("output", {}).get("changes", []) if change.get("success") else []
        risk = self.call_tool(
            "risk_assessment",
            {"table_id": table_id, "changes": changes},
        )

        risk_level = "LOW"
        if risk.get("success"):
            risk_level = risk["output"]["risk_level"]
            sev = {
                "CRITICAL": IncidentSeverity.CRITICAL,
                "HIGH": IncidentSeverity.HIGH,
                "MEDIUM": IncidentSeverity.MEDIUM,
            }.get(risk_level, IncidentSeverity.LOW)
            self.add_finding(
                Finding(
                    title=f"Schema change risk: {risk_level}",
                    severity=sev,
                    kind=EvidenceKind.OBSERVED_FACT,
                    explanation="; ".join(risk["output"]["factors"]),
                    suggested_fix="Coordinate with consumers and update contract version",
                )
            )

        rec = self.call_tool("recommend_action", {"table_id": table_id, "risk_level": risk_level})
        # READ_ONLY recommendations stay informational; gate the real write separately
        if rec.get("success") and rec["output"].get("requires_approval"):
            self.propose_action(
                "publish_contract_version",
                {
                    "table_id": table_id,
                    "risk_level": risk_level,
                    "changelog": f"Schema change on {table_id} ({risk_level})",
                },
                ActionRisk.APPROVAL_REQUIRED,
                rationale="Publish updated data contract version after governance approval",
            )

        if change.get("success") and change["output"]["breaking"]:
            self.add_hypothesis(
                "Schema change will break downstream dbt models or ML features",
                0.85,
                [c["column"] for c in changes[:3]],
            )

        return self.finalize(
            {
                "success": True,
                "table_id": table_id,
                "contract_count": len(contracts.get("output", {}).get("contracts", [])),
                "schema_changes": changes,
                "breaking": change.get("output", {}).get("breaking", False),
                "lineage_downstream": lineage.get("output", {}).get("total_downstream", 0),
                "consumers": consumers.get("output"),
                "risk": risk.get("output"),
                "recommendations": rec.get("output", {}).get("recommendations", []),
            }
        )
