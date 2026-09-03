from __future__ import annotations

from typing import Any

from agent_sdk.base import BaseAgent
from agent_sdk.state import AgentExecution, Finding
from domain.enums import ActionRisk, AgentState, EvidenceKind, IncidentSeverity
from pipeline_sre.rca import merge_candidates, score_from_logs, score_from_metrics, score_from_tests
from tool_sdk.registry import ToolRegistry


class PipelineSREAgent(BaseAgent):
    name = "pipeline_sre"
    description = "Autonomous data pipeline SRE agent for Airflow/dbt/Snowflake/AWS"

    def __init__(self, tools: ToolRegistry, **kwargs: Any) -> None:
        super().__init__(tools, **kwargs)

    def run(self, objective: str, context: dict[str, Any] | None = None) -> AgentExecution:
        context = context or {}
        self.execution = type(self.execution)(agent=self.name, objective=objective)
        dag_id = context.get("dag_id", "insurance_daily_pipeline")
        incident_id = context.get("incident_id", "adhoc")

        self._set_state(AgentState.OBSERVING, f"Loading DAG status for {dag_id}")
        dag_status = self.call_tool("get_airflow_dag_status", {"dag_id": dag_id})
        if not dag_status.get("success"):
            self.execution.state = AgentState.FAILED
            return self.finalize({"success": False, "error": dag_status.get("error")})

        failed_tasks = dag_status["output"]["failed_tasks"]
        self._set_state(AgentState.DETECTING, f"Detected failed tasks: {failed_tasks}")

        logs: list[str] = []
        self._set_state(AgentState.INVESTIGATING, "Collecting task logs and platform signals")
        for task_id in failed_tasks or ["dbt_test_core"]:
            res = self.call_tool("get_task_logs", {"dag_id": dag_id, "task_id": task_id})
            if res.get("success"):
                logs.append(res["output"]["log"])

        dbt_tests = self.call_tool("get_dbt_tests", {"status": "fail"})
        self.call_tool("get_dbt_run", {})
        self.call_tool("get_schema_history", {"table_id": "RAW.CLAIM.claims"})
        profile = self.call_tool("get_data_profile", {"table_id": "RAW.CLAIM.claims"})
        compare = None
        if profile.get("success"):
            compare_res = self.call_tool(
                "compare_historical_metrics",
                {"table_id": "RAW.CLAIM.claims", "column": "incurred_amount"},
            )
            if compare_res.get("success"):
                compare = compare_res["output"]

        cw = self.call_tool("get_cloudwatch_metrics", {"dag_id": dag_id, "hours": 24})
        qh = self.call_tool("get_snowflake_query_history", {"status": "FAILED", "limit": 10})
        self.call_tool("get_dbt_lineage", {"model_unique_id": "model.analytics.fct_claims"})

        self._set_state(AgentState.HYPOTHESIZING, "Forming root-cause hypotheses from rules + anomalies")
        candidates = []
        candidates.extend(score_from_logs(logs))
        if dbt_tests.get("success"):
            candidates.extend(score_from_tests(dbt_tests["output"]["tests"]))
        hints = []
        if cw.get("success"):
            hints.extend(cw["output"].get("anomaly_hints") or [])
        if qh.get("success") and qh["output"]["queries"]:
            hints.append("failed snowflake queries present")
            for q in qh["output"]["queries"]:
                if q.get("error_message"):
                    logs.append(q["error_message"])
            candidates.extend(score_from_logs(logs))
        candidates.extend(score_from_metrics(compare, hints))

        for c in candidates:
            self.add_hypothesis(c.root_cause, c.confidence, c.evidence)

        self._set_state(AgentState.TESTING, "Ranking hypotheses with deterministic RCA engine")
        best = merge_candidates(candidates)
        if not best:
            # fallback: first failed task name heuristic
            best_cause = "upstream_failure" if "extract" in str(failed_tasks) else "unknown"
            self.add_finding(
                Finding(
                    title=best_cause,
                    severity=IncidentSeverity.MEDIUM,
                    kind=EvidenceKind.MODEL_INFERENCE,
                    explanation="Insufficient deterministic signal; low-confidence fallback",
                )
            )
            return self.finalize(
                {
                    "success": False,
                    "root_cause": best_cause,
                    "remediation_success": False,
                    "confidence": 0.2,
                }
            )

        self.add_finding(
            Finding(
                title=best.root_cause,
                severity=IncidentSeverity.HIGH,
                kind=EvidenceKind.OBSERVED_FACT,
                explanation=f"Deterministic RCA selected {best.root_cause}",
                evidence_ids=best.evidence,
                suggested_fix=str(best.remediation_args),
            )
        )

        remediation_success = False
        if best.remediation_tool:
            action = self.propose_action(
                best.remediation_tool,
                best.remediation_args,
                ActionRisk.APPROVAL_REQUIRED
                if best.remediation_tool in {"restart_task", "rerun_dbt_model"}
                else ActionRisk.SAFE_AUTOMATION,
                rationale=f"Remediate {best.root_cause}",
            )
            if action.risk == ActionRisk.SAFE_AUTOMATION:
                # safe tools can run immediately
                if best.remediation_tool == "create_incident_report":
                    args = {
                        "incident_id": incident_id,
                        "root_cause": best.root_cause,
                        "summary": objective,
                        "remediation": best.remediation_args.get("remediation", "see report"),
                        "evidence": best.evidence,
                    }
                    res = self.call_tool("create_incident_report", args)
                    remediation_success = bool(res.get("success"))
                else:
                    res = self.call_tool(best.remediation_tool, best.remediation_args)
                    remediation_success = bool(res.get("success"))
            else:
                self._set_state(
                    AgentState.AWAITING_APPROVAL,
                    f"Proposed {best.remediation_tool} awaiting human approval",
                )

        # Always document
        self.call_tool(
            "create_incident_report",
            {
                "incident_id": incident_id,
                "root_cause": best.root_cause,
                "summary": objective,
                "remediation": f"{best.remediation_tool}:{best.remediation_args}",
                "evidence": best.evidence,
            },
        )

        if self.execution.state != AgentState.AWAITING_APPROVAL:
            self._set_state(AgentState.VERIFYING, "Validating pipeline health")
            validation = self.call_tool("validate_pipeline", {"dag_id": dag_id})
            if validation.get("success"):
                remediation_success = remediation_success or validation["output"]["healthy"]

        return self.finalize(
            {
                "success": best.confidence >= 0.7,
                "root_cause": best.root_cause,
                "confidence": best.confidence,
                "evidence": best.evidence,
                "remediation_success": remediation_success,
                "awaiting_approval": self.execution.state == AgentState.AWAITING_APPROVAL,
            }
        )
