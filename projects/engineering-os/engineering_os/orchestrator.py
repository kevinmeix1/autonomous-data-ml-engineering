from __future__ import annotations

import re
from typing import Any

from agent_sdk.base import BaseAgent
from agent_sdk.state import AgentExecution, EvidenceItem, Finding
from domain.enums import AgentState, EvidenceKind, IncidentSeverity
from tool_sdk.registry import ToolRegistry


# Routing rules: keywords -> ordered agent pipeline
ROUTING_RULES: list[tuple[re.Pattern[str], list[str]]] = [
    (
        re.compile(r"model.*(worse|degrad|perform|auc|drift|calibrat)", re.I),
        ["ml_doctor", "data_quality", "lineage_copilot", "feature_engineering", "retraining"],
    ),
    (
        re.compile(r"pipeline|dag|airflow|failed.*task", re.I),
        ["pipeline_sre", "airflow_optimizer", "data_quality"],
    ),
    (
        re.compile(r"migrat|legacy|snowflake", re.I),
        ["migration", "data_quality", "lineage_copilot"],
    ),
    (
        re.compile(r"lineage|upstream|downstream|impact", re.I),
        ["lineage_copilot", "data_quality"],
    ),
    (
        re.compile(r"retrain|champion|challenger|deploy.*model", re.I),
        ["retraining", "ml_doctor"],
    ),
    (
        re.compile(r"optim|bottleneck|critical path|parallel", re.I),
        ["airflow_optimizer", "pipeline_sre"],
    ),
]


def route_agents(objective: str, context: dict[str, Any] | None = None) -> list[str]:
    """Determine agent pipeline from objective text and optional context hints."""
    context = context or {}
    if context.get("agents"):
        return list(context["agents"])
    for pattern, agents in ROUTING_RULES:
        if pattern.search(objective):
            return agents
    return context.get("default_agents", ["ml_doctor", "pipeline_sre"])


class EngineeringOrchestrator(BaseAgent):
    name = "engineering_os"
    description = "Multi-agent orchestrator routing problems to specialized agents"

    def __init__(self, tools: ToolRegistry | None = None, **kwargs: Any) -> None:
        super().__init__(tools or ToolRegistry(), **kwargs)
        self._sub_executions: list[AgentExecution] = []

    def run(self, objective: str, context: dict[str, Any] | None = None) -> AgentExecution:
        context = context or {}
        self.execution = type(self.execution)(agent=self.name, objective=objective)
        self._sub_executions = []

        agent_names = route_agents(objective, context)
        self._set_state(
            AgentState.OBSERVING,
            f"Routing to agents: {', '.join(agent_names)}",
        )

        combined_evidence: list[dict[str, Any]] = []
        combined_findings: list[dict[str, Any]] = []
        agent_results: dict[str, Any] = {}
        overall_success = True
        stop_on_failure = context.get("stop_on_failure", False)

        from adme_platform.api.agent_factory import create_agent

        for agent_name in agent_names:
            self._set_state(AgentState.INVESTIGATING, f"Delegating to {agent_name}")
            try:
                agent = create_agent(agent_name)
                sub_context = dict(context)
                sub_context["orchestrator_objective"] = objective
                sub_exec = agent.run(objective, sub_context)
                self._sub_executions.append(sub_exec)
                view = sub_exec.public_view()
                agent_results[agent_name] = {
                    "execution_id": sub_exec.execution_id,
                    "state": sub_exec.state.value,
                    "final_result": sub_exec.final_result,
                    "findings_count": len(sub_exec.findings),
                }
                combined_evidence.extend(view.get("evidence", []))
                combined_findings.extend(view.get("findings", []))

                self.execution.evidence.append(
                    EvidenceItem(
                        kind=EvidenceKind.TOOL_RESULT,
                        summary=f"{agent_name} completed with state {sub_exec.state.value}",
                        source=agent_name,
                        data={"final_result": sub_exec.final_result},
                    )
                )

                if sub_exec.final_result and not sub_exec.final_result.get("success", True):
                    overall_success = False
                    if stop_on_failure:
                        break

                # Early exit if retraining not needed
                if agent_name == "ml_doctor" and sub_exec.final_result:
                    domain = sub_exec.final_result.get("problem_domain")
                    if domain == "INFRASTRUCTURE" and "retraining" in agent_names:
                        agent_names = [a for a in agent_names if a != "retraining"]

            except (KeyError, ImportError, ModuleNotFoundError) as exc:
                self.execution.errors.append(f"{agent_name}: {exc}")
                agent_results[agent_name] = {"error": str(exc), "skipped": True}
            except Exception as exc:  # noqa: BLE001
                self.execution.errors.append(f"{agent_name}: {exc}")
                agent_results[agent_name] = {"error": str(exc)}
                overall_success = False

        self.add_finding(
            Finding(
                title=f"Orchestrated {len(agent_results)} agent(s)",
                severity=IncidentSeverity.INFO if overall_success else IncidentSeverity.MEDIUM,
                kind=EvidenceKind.OBSERVED_FACT,
                explanation=f"Pipeline: {' → '.join(agent_names)}",
            )
        )

        combined_view = {
            "objective": objective,
            "agents_invoked": list(agent_results.keys()),
            "agent_results": agent_results,
            "evidence_count": len(combined_evidence),
            "findings_count": len(combined_findings),
            "sub_executions": [e.execution_id for e in self._sub_executions],
        }

        return self.finalize(
            {
                "success": overall_success,
                "routing": agent_names,
                "combined_view": combined_view,
                "agent_results": agent_results,
            }
        )

    def get_sub_executions(self) -> list[AgentExecution]:
        return list(self._sub_executions)
