"""Deliberate failure injection for agent verification."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from data_generation.generator import SyntheticPlatform
from domain.enums import PipelineStatus, QualityDimension
from domain.models import DbtTestResult


def inject_failure(platform: SyntheticPlatform, failure_type: str) -> SyntheticPlatform:
    """Mutate platform state to inject a known failure type."""
    dag = platform.dags[0]
    now = datetime.now(timezone.utc)

    def fail(task_id: str, log: str) -> None:
        for t in dag.tasks:
            if t.task_id == task_id:
                t.status = PipelineStatus.FAILED
                t.log_excerpt = log
                platform.task_logs[f"{dag.dag_id}.{task_id}"] = log
        dag.last_run_status = PipelineStatus.FAILED

    if failure_type == "break_dag":
        fail("dbt_run_core", "[ERROR] injected DAG break\n")
    elif failure_type == "corrupt_schema":
        fail("dbt_run_staging", "[ERROR] unexpected value REOPENED in claim_status\n")
    elif failure_type == "inject_duplicates":
        platform.dbt_tests.append(
            DbtTestResult(
                test_id=str(uuid4()),
                test_name="unique_fct_claims_claim_id",
                model_unique_id="model.analytics.fct_claims",
                status="fail",
                failures=99,
                dimension=QualityDimension.UNIQUENESS,
                message="injected duplicates",
                executed_at=now,
                column_name="claim_id",
            )
        )
        fail("dbt_test_core", "[ERROR] unique_fct_claims_claim_id failed\n")
    elif failure_type == "feature_drift":
        model = platform.models[0]
        model.metrics["auc"] = max(0.5, float(model.metrics.get("auc", 0.8)) - 0.08)
        model.metrics["psi_avg_incurred_12m"] = 0.35
    elif failure_type == "model_drift":
        model = platform.models[0]
        model.metrics["auc"] = 0.62
        model.metrics["calibration_ece"] = 0.18
    elif failure_type == "increase_query_cost":
        for q in platform.queries[:5]:
            q.bytes_scanned *= 20
            q.credits_used *= 20
    elif failure_type == "break_dbt_dependency":
        fail("feature_build", "[ERROR] dependency model.analytics.fct_claims missing\n")
    else:
        raise ValueError(f"Unknown failure_type: {failure_type}")
    return platform
