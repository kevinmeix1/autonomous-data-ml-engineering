from __future__ import annotations

from typing import Any

from agent_sdk.base import BaseAgent
from agent_sdk.state import AgentExecution, Finding
from domain.enums import ActionRisk, AgentState, EvidenceKind, IncidentSeverity
from tool_sdk.registry import ToolRegistry


class SnowflakeOptimizerAgent(BaseAgent):
    name = "snowflake_optimizer"
    description = "Autonomous Snowflake cost optimization agent"

    def __init__(self, tools: ToolRegistry, **kwargs: Any) -> None:
        super().__init__(tools, **kwargs)

    def run(self, objective: str, context: dict[str, Any] | None = None) -> AgentExecution:
        context = context or {}
        self.execution = type(self.execution)(agent=self.name, objective=objective)
        model_id = context.get("model_unique_id", "model.analytics.fct_claims")

        self._set_state(AgentState.OBSERVING, "Discovering expensive queries")
        expensive = self.call_tool("list_expensive_queries", {"limit": 5})
        if not expensive.get("success"):
            self.execution.state = AgentState.FAILED
            return self.finalize({"success": False, "error": expensive.get("error")})

        self._set_state(AgentState.DETECTING, "Ranking cost hotspots")
        wh = self.call_tool("get_warehouse_utilization", {"hours": 24})
        tables = self.call_tool("get_table_sizes", {"limit": 10})
        model_cost = self.call_tool("get_dbt_model_cost", {"model_unique_id": model_id})

        recommendations: list[dict[str, Any]] = []
        if model_cost.get("success") and model_cost["output"]["total_credits"] > 0.5:
            self.add_hypothesis(
                f"Model {model_id} is a top cost driver",
                0.8,
                [f"credits={model_cost['output']['total_credits']}"],
            )
            est = self.call_tool(
                "estimate_savings",
                {
                    "optimization_type": "incremental_filter",
                    "target": model_id,
                    "params": {"expected_pct": 0.35},
                },
            )
            if est.get("success"):
                recommendations.append(est["output"])
                self.add_finding(
                    Finding(
                        title="Incremental filter optimization",
                        severity=IncidentSeverity.HIGH,
                        kind=EvidenceKind.RECOMMENDED_ACTION,
                        explanation=(
                            f"Predicted savings {est['output']['predicted_savings_usd']} USD "
                            f"({est['output']['predicted_savings_pct']}%)"
                        ),
                        suggested_fix="Tighten incremental watermark on report_date",
                    )
                )

        if wh.get("success"):
            for row in wh["output"]["warehouses"]:
                if row["max_queued_overload"] > 120:
                    est = self.call_tool(
                        "estimate_savings",
                        {
                            "optimization_type": "warehouse_downsize",
                            "target": row["warehouse"],
                            "params": {"expected_pct": 0.2},
                        },
                    )
                    if est.get("success"):
                        recommendations.append(est["output"])

        top_target = recommendations[0] if recommendations else None
        optimization_id = None
        measured = None

        if top_target:
            self._set_state(AgentState.REMEDIATING, "Proposing optimization")
            action = self.propose_action(
                "apply_optimization",
                {
                    "optimization_type": top_target["optimization_type"],
                    "target": top_target["target"],
                    "params": {},
                },
                ActionRisk.APPROVAL_REQUIRED,
                rationale=f"Apply {top_target['optimization_type']} for cost reduction",
            )
            if action.approval_required:
                self._set_state(AgentState.AWAITING_APPROVAL, "Optimization awaiting approval")
            else:
                applied = self.call_tool(
                    "apply_optimization",
                    {
                        "optimization_type": top_target["optimization_type"],
                        "target": top_target["target"],
                        "params": {},
                    },
                    approved=True,
                )
                if applied.get("success"):
                    optimization_id = applied["output"]["optimization_id"]
                    measured = self.call_tool(
                        "measure_impact",
                        {
                            "optimization_id": optimization_id,
                            "baseline_credits": top_target["baseline_credits"],
                            "predicted_savings_credits": top_target["predicted_savings_credits"],
                        },
                    )

        return self.finalize(
            {
                "success": True,
                "expensive_query_credits": expensive["output"]["total_credits"],
                "model_cost": model_cost.get("output"),
                "table_count": len(tables.get("output", {}).get("tables", [])),
                "recommendations": recommendations,
                "optimization_id": optimization_id,
                "impact": measured.get("output") if measured else None,
                "awaiting_approval": self.execution.state == AgentState.AWAITING_APPROVAL,
            }
        )
