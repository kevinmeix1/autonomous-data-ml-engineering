from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass
class RCACandidate:
    root_cause: str
    confidence: float
    evidence: list[str]
    remediation_tool: str | None
    remediation_args: dict[str, Any]


RULES: list[tuple[str, str, float]] = [
    (r"Connection refused|SourceExtractError|SFTP", "upstream_failure", 0.92),
    (r"unexpected value|accepted_values|schema|REOPENED", "schema_change", 0.9),
    (r"Partition not found|s3://.*dt=", "missing_partition", 0.9),
    (r"not_null|null spike", "null_spike", 0.88),
    (r"unique_.*claim|duplicate", "duplicate_records", 0.9),
    (r"freshness|SLA", "data_freshness_failure", 0.88),
    (r"timeout|000630|57014", "snowflake_query_timeout", 0.9),
    (r"queued_overload|overload", "warehouse_overload", 0.87),
    (r"invalid identifier|SQL compilation error", "invalid_sql", 0.93),
    (r"Feature table missing|upstream .* failed", "downstream_dependency_failure", 0.85),
]


def score_from_logs(logs: list[str]) -> list[RCACandidate]:
    text = "\n".join(logs)
    candidates: list[RCACandidate] = []
    for pattern, cause, conf in RULES:
        if re.search(pattern, text, flags=re.IGNORECASE):
            candidates.append(
                RCACandidate(
                    root_cause=cause,
                    confidence=conf,
                    evidence=[f"log_match:{pattern}"],
                    remediation_tool=_remediation_for(cause)[0],
                    remediation_args=_remediation_for(cause)[1],
                )
            )
    return candidates


def score_from_tests(tests: list[dict[str, Any]]) -> list[RCACandidate]:
    out: list[RCACandidate] = []
    for t in tests:
        if t.get("status") != "fail":
            continue
        name = (t.get("test_name") or "").lower()
        msg = (t.get("message") or "").lower()
        if "unique" in name or "duplicate" in msg:
            cause = "duplicate_records"
        elif "not_null" in name or "null" in msg:
            cause = "null_spike"
        elif "accepted_values" in name or "validity" in str(t.get("dimension", "")).lower():
            cause = "schema_change"
        elif "freshness" in name or "freshness" in msg:
            cause = "data_freshness_failure"
        else:
            continue
        tool, args = _remediation_for(cause)
        out.append(
            RCACandidate(
                root_cause=cause,
                confidence=0.86,
                evidence=[f"failed_test:{t.get('test_name')}"],
                remediation_tool=tool,
                remediation_args=args,
            )
        )
    return out


def score_from_metrics(compare: dict[str, Any] | None, warehouse_hints: list[str]) -> list[RCACandidate]:
    out: list[RCACandidate] = []
    if compare and compare.get("is_anomaly"):
        out.append(
            RCACandidate(
                root_cause="null_spike",
                confidence=min(0.95, 0.7 + abs(float(compare.get("z_score", 0))) * 0.05),
                evidence=[f"z_score={compare.get('z_score')}"],
                remediation_tool="rerun_dbt_model",
                remediation_args={"model_unique_id": "model.analytics.fct_claims"},
            )
        )
    for hint in warehouse_hints:
        if "overload" in hint.lower() or "spike" in hint.lower():
            out.append(
                RCACandidate(
                    root_cause="warehouse_overload",
                    confidence=0.8,
                    evidence=[hint],
                    remediation_tool="restart_task",
                    remediation_args={"dag_id": "insurance_daily_pipeline", "task_id": "dbt_run_core"},
                )
            )
    return out


def merge_candidates(candidates: list[RCACandidate]) -> RCACandidate | None:
    if not candidates:
        return None
    by_cause: dict[str, RCACandidate] = {}
    for c in candidates:
        if c.root_cause not in by_cause or c.confidence > by_cause[c.root_cause].confidence:
            by_cause[c.root_cause] = c
        else:
            by_cause[c.root_cause].evidence.extend(c.evidence)
            by_cause[c.root_cause].confidence = min(
                0.99, by_cause[c.root_cause].confidence + 0.03
            )
    return sorted(by_cause.values(), key=lambda x: x.confidence, reverse=True)[0]


def _remediation_for(cause: str) -> tuple[str | None, dict[str, Any]]:
    mapping = {
        "upstream_failure": (
            "restart_task",
            {"dag_id": "insurance_daily_pipeline", "task_id": "extract_claims"},
        ),
        "schema_change": (
            "create_incident_report",
            {
                "incident_id": "schema",
                "root_cause": "schema_change",
                "summary": "Update accepted values / contract",
                "remediation": "Update dbt accepted_values and data contract",
            },
        ),
        "missing_partition": (
            "restart_task",
            {"dag_id": "insurance_daily_pipeline", "task_id": "load_raw_claims"},
        ),
        "null_spike": (
            "rerun_dbt_model",
            {"model_unique_id": "model.analytics.fct_claims"},
        ),
        "duplicate_records": (
            "rerun_dbt_model",
            {"model_unique_id": "model.analytics.fct_claims"},
        ),
        "data_freshness_failure": (
            "restart_task",
            {"dag_id": "insurance_daily_pipeline", "task_id": "extract_claims"},
        ),
        "snowflake_query_timeout": (
            "rerun_dbt_model",
            {"model_unique_id": "model.analytics.fct_claims"},
        ),
        "warehouse_overload": (
            "restart_task",
            {"dag_id": "insurance_daily_pipeline", "task_id": "dbt_run_core"},
        ),
        "invalid_sql": (
            "create_incident_report",
            {
                "incident_id": "invalid_sql",
                "root_cause": "invalid_sql",
                "summary": "Fix SQL identifier typo",
                "remediation": "Correct POLICY_RISK_SCOR typo and rerun",
            },
        ),
        "downstream_dependency_failure": (
            "restart_task",
            {"dag_id": "insurance_daily_pipeline", "task_id": "feature_build"},
        ),
    }
    return mapping.get(cause, (None, {}))
