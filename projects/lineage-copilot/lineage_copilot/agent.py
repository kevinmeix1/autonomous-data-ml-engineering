from __future__ import annotations

from typing import Any

from agent_sdk.base import BaseAgent
from agent_sdk.state import AgentExecution, Finding
from domain.enums import AgentState, EvidenceKind, IncidentSeverity
from tool_sdk.registry import ToolRegistry


class LineageCopilotAgent(BaseAgent):
    name = "lineage_copilot"
    description = "Insurance domain lineage copilot — policies, claims, features, models"

    def __init__(self, tools: ToolRegistry, **kwargs: Any) -> None:
        super().__init__(tools, **kwargs)

    def run(self, objective: str, context: dict[str, Any] | None = None) -> AgentExecution:
        context = context or {}
        self.execution = type(self.execution)(agent=self.name, objective=objective)
        node_id = context.get("node_id", "RAW.CLAIM.claims")
        model_id = context.get("model_id", "ml.claims_severity_v3")
        feature = context.get("feature_name", "avg_incurred_12m")

        self._set_state(AgentState.OBSERVING, f"Exploring lineage from {node_id}")
        upstream = self.call_tool("find_upstream", {"node_id": node_id, "depth": 3})
        downstream = self.call_tool("find_downstream", {"node_id": node_id, "depth": 5})

        self._set_state(AgentState.INVESTIGATING, "Tracing features and model dependencies")
        self.call_tool("find_feature_origin", {"feature_name": feature})
        models = self.call_tool("find_models_using_table", {"table_id": node_id})
        tables = self.call_tool("find_tables_used_by_model", {"model_id": model_id})

        self._set_state(AgentState.HYPOTHESIZING, "Explaining transformations and impact")
        impact = self.call_tool("identify_impact", {"node_id": node_id})
        if upstream.get("success") and downstream.get("success"):
            up_nodes = upstream["output"].get("nodes", [])
            down_nodes = downstream["output"].get("nodes", [])
            if up_nodes and down_nodes:
                self.call_tool(
                    "explain_transformation",
                    {"source_id": up_nodes[0]["id"], "target_id": down_nodes[0]["id"]},
                )

        evidence_count = len(upstream.get("output", {}).get("evidence", []))
        self.add_finding(
            Finding(
                title=f"Lineage traced for {node_id}",
                severity=IncidentSeverity.INFO,
                kind=EvidenceKind.OBSERVED_FACT,
                explanation=f"{evidence_count} lineage edges cited from STORE.lineage graph",
                evidence_ids=[e.get("edge_id", "") for e in upstream.get("output", {}).get("evidence", [])[:5]],
            )
        )

        return self.finalize(
            {
                "success": True,
                "node_id": node_id,
                "upstream_count": len(upstream.get("output", {}).get("nodes", [])),
                "downstream_count": len(downstream.get("output", {}).get("nodes", [])),
                "models_using_table": models.get("output", {}).get("models", []),
                "tables_for_model": tables.get("output", {}).get("tables", []),
                "total_impacted": impact.get("output", {}).get("total_impacted", 0),
                "lineage_evidence_cited": evidence_count,
            }
        )
