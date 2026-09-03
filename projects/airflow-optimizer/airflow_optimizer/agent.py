from __future__ import annotations

from typing import Any

from agent_sdk.base import BaseAgent
from agent_sdk.state import AgentExecution, Finding
from domain.enums import ActionRisk, AgentState, EvidenceKind, IncidentSeverity
from tool_sdk.registry import ToolRegistry


class AirflowOptimizerAgent(BaseAgent):
    name = "airflow_optimizer"
    description = "Airflow DAG optimizer — critical path, bottlenecks, and recommendations"

    def __init__(self, tools: ToolRegistry, **kwargs: Any) -> None:
        super().__init__(tools, **kwargs)

    def run(self, objective: str, context: dict[str, Any] | None = None) -> AgentExecution:
        context = context or {}
        self.execution = type(self.execution)(agent=self.name, objective=objective)
        dag_id = context.get("dag_id", "insurance_daily_pipeline")

        self._set_state(AgentState.OBSERVING, f"Loading DAG graph for {dag_id}")
        graph = self.call_tool("get_dag_graph", {"dag_id": dag_id})
        if not graph.get("success"):
            self.execution.state = AgentState.FAILED
            return self.finalize({"success": False, "error": graph.get("error")})

        self._set_state(AgentState.INVESTIGATING, "Computing critical path and bottlenecks")
        cp = self.call_tool("compute_critical_path", {"dag_id": dag_id})
        durations = self.call_tool("analyze_task_durations", {"dag_id": dag_id})
        bottlenecks = self.call_tool("find_bottlenecks", {"dag_id": dag_id})

        self._set_state(AgentState.HYPOTHESIZING, "Generating optimization recommendations")
        recs = self.call_tool("recommend_dag_changes", {"dag_id": dag_id})

        bn_list = bottlenecks.get("output", {}).get("bottlenecks", [])
        if bn_list:
            self.add_finding(
                Finding(
                    title=f"{len(bn_list)} bottleneck(s) identified",
                    severity=IncidentSeverity.MEDIUM,
                    kind=EvidenceKind.OBSERVED_FACT,
                    explanation=bn_list[0].get("reason", "") if isinstance(bn_list[0], dict) else bn_list[0].reason,
                    suggested_fix="See recommend_dag_changes",
                )
            )

        recommendations = recs.get("output", {}).get("recommendations", [])
        if recommendations and context.get("auto_apply"):
            top = recommendations[0]
            self.propose_action(
                "apply_dag_change",
                {
                    "dag_id": dag_id,
                    "change_type": top.get("type") if isinstance(top, dict) else top.type,
                    "task_ids": top.get("task_ids") if isinstance(top, dict) else top.task_ids,
                },
                ActionRisk.APPROVAL_REQUIRED,
                rationale="Apply top DAG optimization recommendation",
            )

        return self.finalize(
            {
                "success": True,
                "dag_id": dag_id,
                "max_depth": graph["output"].get("max_depth"),
                "critical_path": cp.get("output", {}).get("critical_path", []),
                "total_duration_seconds": cp.get("output", {}).get("total_duration_seconds"),
                "bottleneck_task": cp.get("output", {}).get("bottleneck_task"),
                "bottlenecks": bn_list,
                "recommendations": recommendations,
                "task_durations": durations.get("output", {}).get("tasks", []),
            }
        )
