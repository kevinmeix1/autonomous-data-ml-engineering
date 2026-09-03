from __future__ import annotations

import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from domain.enums import IncidentSeverity, PipelineStatus, QualityDimension
from domain.models import (
    AirflowDag,
    AirflowTask,
    ColumnSchema,
    DataContract,
    DbtModel,
    DbtTestResult,
    FeatureDefinition,
    Incident,
    LineageEdge,
    MLModel,
    QueryHistoryEntry,
    SchemaVersion,
    TableMetadata,
    WarehouseMetric,
)
from pydantic import BaseModel, Field


INSURANCE_TABLES = [
    ("RAW", "POLICY", "policies"),
    ("RAW", "CLAIM", "claims"),
    ("RAW", "CUSTOMER", "customers"),
    ("RAW", "EXPOSURE", "exposures"),
    ("RAW", "PREMIUM", "premiums"),
    ("ANALYTICS", "CORE", "dim_policy"),
    ("ANALYTICS", "CORE", "dim_customer"),
    ("ANALYTICS", "CORE", "fct_claims"),
    ("ANALYTICS", "CORE", "fct_premiums"),
    ("ANALYTICS", "ML", "feat_claim_severity"),
    ("ANALYTICS", "ML", "feat_policy_risk"),
    ("ANALYTICS", "ML", "training_claims_model"),
]

FAILURE_TYPES = [
    "upstream_failure",
    "schema_change",
    "missing_partition",
    "null_spike",
    "duplicate_records",
    "data_freshness_failure",
    "snowflake_query_timeout",
    "warehouse_overload",
    "invalid_sql",
    "downstream_dependency_failure",
]


class SyntheticPlatform(BaseModel):
    generated_at: datetime
    seed: int
    tables: list[TableMetadata] = Field(default_factory=list)
    schema_versions: list[SchemaVersion] = Field(default_factory=list)
    dags: list[AirflowDag] = Field(default_factory=list)
    dbt_models: list[DbtModel] = Field(default_factory=list)
    dbt_tests: list[DbtTestResult] = Field(default_factory=list)
    queries: list[QueryHistoryEntry] = Field(default_factory=list)
    warehouse_metrics: list[WarehouseMetric] = Field(default_factory=list)
    lineage: list[LineageEdge] = Field(default_factory=list)
    features: list[FeatureDefinition] = Field(default_factory=list)
    models: list[MLModel] = Field(default_factory=list)
    contracts: list[DataContract] = Field(default_factory=list)
    incidents: list[Incident] = Field(default_factory=list)
    cloudwatch_metrics: list[dict[str, Any]] = Field(default_factory=list)
    task_logs: dict[str, str] = Field(default_factory=dict)
    data_profiles: dict[str, dict[str, Any]] = Field(default_factory=dict)
    scenarios: list[dict[str, Any]] = Field(default_factory=list)
    dbt_sql: dict[str, str] = Field(default_factory=dict)

    def to_files(self, output_dir: str | Path) -> None:
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        payload = self.model_dump(mode="json")
        (out / "platform.json").write_text(json.dumps(payload, indent=2, default=str))
        for key in [
            "tables",
            "dags",
            "dbt_models",
            "dbt_tests",
            "queries",
            "lineage",
            "features",
            "models",
            "contracts",
            "incidents",
            "scenarios",
            "warehouse_metrics",
            "cloudwatch_metrics",
            "schema_versions",
            "dbt_sql",
        ]:
            (out / f"{key}.json").write_text(json.dumps(payload[key], indent=2, default=str))
        (out / "task_logs.json").write_text(json.dumps(self.task_logs, indent=2))
        (out / "data_profiles.json").write_text(json.dumps(self.data_profiles, indent=2, default=str))


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _cols_for(table: str) -> list[ColumnSchema]:
    common = {
        "policies": [
            ColumnSchema(name="policy_id", data_type="VARCHAR", nullable=False, is_primary_key=True),
            ColumnSchema(name="customer_id", data_type="VARCHAR", nullable=False),
            ColumnSchema(name="effective_date", data_type="DATE", nullable=False),
            ColumnSchema(name="expiration_date", data_type="DATE", nullable=False),
            ColumnSchema(name="premium_amount", data_type="NUMBER", nullable=False),
            ColumnSchema(
                name="coverage_type",
                data_type="VARCHAR",
                nullable=False,
                enum_values=["GL", "PROPERTY", "AUTO", "WORKERS_COMP"],
            ),
            ColumnSchema(
                name="status",
                data_type="VARCHAR",
                nullable=False,
                enum_values=["ACTIVE", "CANCELLED", "EXPIRED"],
            ),
        ],
        "claims": [
            ColumnSchema(name="claim_id", data_type="VARCHAR", nullable=False, is_primary_key=True),
            ColumnSchema(name="policy_id", data_type="VARCHAR", nullable=False),
            ColumnSchema(name="loss_date", data_type="DATE", nullable=False),
            ColumnSchema(name="report_date", data_type="DATE", nullable=False),
            ColumnSchema(
                name="claim_status",
                data_type="VARCHAR",
                nullable=False,
                enum_values=["OPEN", "CLOSED", "LITIGATION", "DENIED"],
            ),
            ColumnSchema(name="incurred_amount", data_type="NUMBER", nullable=True),
            ColumnSchema(name="paid_amount", data_type="NUMBER", nullable=True),
        ],
        "customers": [
            ColumnSchema(name="customer_id", data_type="VARCHAR", nullable=False, is_primary_key=True),
            ColumnSchema(name="legal_name", data_type="VARCHAR", nullable=False),
            ColumnSchema(name="industry_naics", data_type="VARCHAR", nullable=True),
            ColumnSchema(name="state", data_type="VARCHAR", nullable=False),
            ColumnSchema(name="risk_tier", data_type="VARCHAR", nullable=True),
        ],
    }
    base = table.split("_")[-1] if "_" in table else table
    if base in common:
        return common[base]
    if "feat_" in table or table.startswith("feat"):
        return [
            ColumnSchema(name="entity_id", data_type="VARCHAR", nullable=False, is_primary_key=True),
            ColumnSchema(name="as_of_ts", data_type="TIMESTAMP_NTZ", nullable=False),
            ColumnSchema(name="feature_value", data_type="FLOAT", nullable=True),
        ]
    if table.startswith(("fct_", "dim_", "training")):
        return [
            ColumnSchema(name="id", data_type="VARCHAR", nullable=False, is_primary_key=True),
            ColumnSchema(name="policy_id", data_type="VARCHAR", nullable=True),
            ColumnSchema(name="claim_id", data_type="VARCHAR", nullable=True),
            ColumnSchema(name="amount", data_type="NUMBER", nullable=True),
            ColumnSchema(name="event_date", data_type="DATE", nullable=True),
            ColumnSchema(name="updated_at", data_type="TIMESTAMP_NTZ", nullable=True),
        ]
    return [
        ColumnSchema(name="id", data_type="VARCHAR", nullable=False, is_primary_key=True),
        ColumnSchema(name="payload", data_type="VARIANT", nullable=True),
        ColumnSchema(name="loaded_at", data_type="TIMESTAMP_NTZ", nullable=False),
    ]


def _make_failure(
    ftype: str,
    idx: int,
    rng: random.Random,
    now: datetime,
) -> tuple[Incident, dict[str, Any], dict[str, Any]]:
    incident_id = f"INC-{idx:04d}"
    titles = {
        "upstream_failure": "Upstream extract_claims task failed",
        "schema_change": "Schema change broke stg_claims",
        "missing_partition": "Missing partition for claims load date",
        "null_spike": "Null spike in incurred_amount",
        "duplicate_records": "Duplicate claim_id in fct_claims",
        "data_freshness_failure": "Claims table freshness SLA breached",
        "snowflake_query_timeout": "dbt_run_core Snowflake timeout",
        "warehouse_overload": "TRANSFORM_WH overload delaying pipeline",
        "invalid_sql": "Invalid SQL in feat_policy_risk model",
        "downstream_dependency_failure": "score_claims_model failed due to upstream",
    }
    severity = (
        IncidentSeverity.HIGH
        if ftype in {"schema_change", "duplicate_records", "invalid_sql"}
        else IncidentSeverity.MEDIUM
    )
    incident = Incident(
        incident_id=incident_id,
        title=titles[ftype],
        severity=severity,
        status="open",
        source_system="airflow" if ftype in {
            "upstream_failure",
            "missing_partition",
            "snowflake_query_timeout",
            "warehouse_overload",
            "downstream_dependency_failure",
        } else "dbt",
        detected_at=now - timedelta(minutes=rng.randint(10, 180)),
        ground_truth_root_cause=ftype,
        affected_assets=["insurance_daily_pipeline", "model.analytics.fct_claims"],
        summary=titles[ftype],
        metadata={"failure_type": ftype},
    )
    scenario = {
        "scenario_id": f"scn-{ftype}-{idx:03d}",
        "agent": "pipeline_sre",
        "title": titles[ftype],
        "description": f"Investigate incident {incident_id}: {titles[ftype]}",
        "failure_type": ftype,
        "ground_truth_root_cause": ftype,
        "expected_tools": [
            "get_airflow_dag_status",
            "get_task_logs",
            "get_dbt_run",
            "get_dbt_tests",
            "get_table_metadata",
        ],
        "context": {"incident_id": incident_id, "dag_id": "insurance_daily_pipeline"},
        "difficulty": "medium",
    }
    return incident, scenario, {"type": ftype}


def _apply_mutations(platform: SyntheticPlatform, mutations: dict[str, Any]) -> None:
    ftype = mutations["type"]
    dag = platform.dags[0]
    now = platform.generated_at

    def fail_task(task_id: str, log: str) -> None:
        for t in dag.tasks:
            if t.task_id == task_id:
                t.status = PipelineStatus.FAILED
                t.log_excerpt = log
                platform.task_logs[f"{dag.dag_id}.{task_id}"] = log
        dag.last_run_status = PipelineStatus.FAILED

    if ftype == "upstream_failure":
        fail_task(
            "extract_claims",
            "[ERROR] Connection refused to claims source SFTP\nTraceback: SourceExtractError\n",
        )
        for t in dag.tasks:
            if t.task_id in {"load_raw_claims", "dbt_run_staging"}:
                t.status = PipelineStatus.SKIPPED
    elif ftype == "schema_change":
        fail_task(
            "dbt_run_staging",
            "[ERROR] Database Error in model stg_claims\ncolumn claim_status unexpected value REOPENED\n",
        )
        platform.dbt_tests.append(
            DbtTestResult(
                test_id=str(uuid4()),
                test_name="accepted_values_stg_claims_claim_status",
                model_unique_id="model.analytics.stg_claims",
                status="fail",
                failures=1284,
                dimension=QualityDimension.VALIDITY,
                message="Found values not in accepted set",
                executed_at=now,
                column_name="claim_status",
            )
        )
    elif ftype == "missing_partition":
        fail_task(
            "load_raw_claims",
            "[ERROR] Partition not found: s3://claims-landing/dt=2026-08-09/\n",
        )
    elif ftype == "null_spike":
        platform.data_profiles["RAW.CLAIM.claims"]["null_rates"]["incurred_amount"] = 0.42
        platform.dbt_tests.append(
            DbtTestResult(
                test_id=str(uuid4()),
                test_name="not_null_fct_claims_incurred_amount",
                model_unique_id="model.analytics.fct_claims",
                status="fail",
                failures=9200,
                dimension=QualityDimension.COMPLETENESS,
                message="null spike detected",
                executed_at=now,
                column_name="incurred_amount",
            )
        )
        fail_task("dbt_test_core", "[ERROR] dbt test failed: not_null_fct_claims_incurred_amount\n")
    elif ftype == "duplicate_records":
        platform.dbt_tests.append(
            DbtTestResult(
                test_id=str(uuid4()),
                test_name="unique_fct_claims_claim_id",
                model_unique_id="model.analytics.fct_claims",
                status="fail",
                failures=356,
                dimension=QualityDimension.UNIQUENESS,
                message="duplicate claim_id after replay",
                executed_at=now,
                column_name="claim_id",
            )
        )
        fail_task("dbt_test_core", "[ERROR] dbt test failed: unique_fct_claims_claim_id\n")
    elif ftype == "data_freshness_failure":
        platform.data_profiles["RAW.CLAIM.claims"]["freshness_hours"] = 48
        fail_task(
            "dbt_test_core",
            "[ERROR] freshness check failed for RAW.CLAIM.claims SLA=2h actual=48h\n",
        )
    elif ftype == "snowflake_query_timeout":
        fail_task(
            "dbt_run_core",
            "[ERROR] 000630 (57014): Statement reached its timeout and was canceled.\n",
        )
        if platform.queries:
            platform.queries[0].status = "FAILED"
            platform.queries[0].error_message = (
                "Statement reached its timeout of 3600 second(s) and was canceled."
            )
            platform.queries[0].dbt_model = "model.analytics.fct_claims"
    elif ftype == "warehouse_overload":
        for m in platform.warehouse_metrics:
            if m.warehouse == "TRANSFORM_WH" and m.timestamp > now - timedelta(hours=6):
                m.queued_overload_time = 900
                m.avg_queued = 12
        fail_task(
            "dbt_run_core",
            "[WARN] warehouse TRANSFORM_WH queued_overload_time=900s\n[ERROR] query delayed then cancelled\n",
        )
    elif ftype == "invalid_sql":
        fail_task(
            "feature_build",
            "[ERROR] SQL compilation error: invalid identifier POLICY_RISK_SCOR\nmodel: feat_policy_risk\n",
        )
    elif ftype == "downstream_dependency_failure":
        fail_task("feature_build", "[ERROR] upstream dbt_test_core failed\n")
        fail_task("score_claims_model", "[ERROR] Feature table missing; cannot score\n")


def generate_platform(seed: int = 42, n_incidents: int = 40) -> SyntheticPlatform:
    rng = random.Random(seed)
    now = _now()
    platform = SyntheticPlatform(generated_at=now, seed=seed)

    for db, schema, table in INSURANCE_TABLES:
        tid = f"{db}.{schema}.{table}"
        cols = _cols_for(table)
        meta = TableMetadata(
            table_id=tid,
            database=db,
            schema_name=schema,
            table_name=table,
            columns=cols,
            row_count=rng.randint(10_000, 5_000_000),
            bytes=rng.randint(50_000_000, 20_000_000_000),
            last_altered=now - timedelta(hours=rng.randint(1, 72)),
            tags=["insurance", schema.lower()],
        )
        platform.tables.append(meta)
        platform.schema_versions.append(
            SchemaVersion(
                version_id=str(uuid4()),
                table_id=tid,
                version=1,
                columns=cols,
                changed_at=now - timedelta(days=30),
                change_summary="initial schema",
            )
        )
        platform.data_profiles[tid] = {
            "row_count": meta.row_count,
            "null_rates": {c.name: rng.random() * 0.05 for c in cols},
            "distinct_counts": {c.name: rng.randint(100, 100000) for c in cols},
            "freshness_hours": rng.uniform(0.5, 36),
            "historical_null_rates": {
                c.name: [rng.random() * 0.05 for _ in range(14)] for c in cols
            },
        }

    claims = next(t for t in platform.tables if t.table_name == "claims")
    new_cols = [c.model_copy(deep=True) for c in claims.columns]
    for c in new_cols:
        if c.name == "claim_status":
            c.enum_values = ["OPEN", "CLOSED", "LITIGATION", "DENIED", "REOPENED"]
    new_cols.append(ColumnSchema(name="claim_status_v2", data_type="VARCHAR", nullable=True))
    platform.schema_versions.append(
        SchemaVersion(
            version_id=str(uuid4()),
            table_id=claims.table_id,
            version=2,
            columns=new_cols,
            changed_at=now - timedelta(hours=6),
            change_summary="claim_status enum extended; claim_status_v2 added",
            changed_by="source-system",
        )
    )
    claims.columns = new_cols

    model_specs = [
        ("model.analytics.stg_claims", "stg_claims", "view", ["RAW.CLAIM.claims"], False),
        ("model.analytics.stg_policies", "stg_policies", "view", ["RAW.POLICY.policies"], False),
        ("model.analytics.dim_policy", "dim_policy", "table", ["model.analytics.stg_policies"], False),
        (
            "model.analytics.fct_claims",
            "fct_claims",
            "incremental",
            ["model.analytics.stg_claims", "model.analytics.dim_policy"],
            True,
        ),
        (
            "model.analytics.feat_claim_severity",
            "feat_claim_severity",
            "table",
            ["model.analytics.fct_claims"],
            False,
        ),
        (
            "model.analytics.feat_policy_risk",
            "feat_policy_risk",
            "table",
            ["model.analytics.dim_policy", "model.analytics.fct_claims"],
            False,
        ),
        (
            "model.analytics.training_claims_model",
            "training_claims_model",
            "table",
            ["model.analytics.feat_claim_severity", "model.analytics.feat_policy_risk"],
            False,
        ),
    ]
    for uid, name, mat, deps, incr in model_specs:
        platform.dbt_models.append(
            DbtModel(
                unique_id=uid,
                name=name,
                schema_name="ML" if name.startswith("feat") or name.startswith("training") else "CORE",
                materialization=mat,
                path=f"models/{name}.sql",
                depends_on=deps,
                columns=["id", "policy_id", "amount", "event_date"],
                has_tests=name in {"fct_claims", "dim_policy", "stg_claims"},
                has_docs=name != "stg_claims",
                is_incremental=incr,
                estimated_bytes_scanned=rng.randint(1_000_000_000, 50_000_000_000),
            )
        )
        platform.dbt_sql[uid] = _sample_sql(name, incr)

    edges = [
        ("RAW.CLAIM.claims", "model.analytics.stg_claims", "source", "dbt_model", "select/rename"),
        ("RAW.POLICY.policies", "model.analytics.stg_policies", "source", "dbt_model", "select/rename"),
        ("model.analytics.stg_policies", "model.analytics.dim_policy", "dbt_model", "dbt_model", "dedupe"),
        ("model.analytics.stg_claims", "model.analytics.fct_claims", "dbt_model", "dbt_model", "incremental join"),
        ("model.analytics.dim_policy", "model.analytics.fct_claims", "dbt_model", "dbt_model", "join"),
        ("model.analytics.fct_claims", "model.analytics.feat_claim_severity", "dbt_model", "feature", "aggregations"),
        ("model.analytics.dim_policy", "model.analytics.feat_policy_risk", "dbt_model", "feature", "risk scoring"),
        ("model.analytics.fct_claims", "model.analytics.feat_policy_risk", "dbt_model", "feature", "claim history"),
        (
            "model.analytics.feat_claim_severity",
            "model.analytics.training_claims_model",
            "feature",
            "training_table",
            "join features",
        ),
        (
            "model.analytics.feat_policy_risk",
            "model.analytics.training_claims_model",
            "feature",
            "training_table",
            "join features",
        ),
        ("model.analytics.training_claims_model", "ml.claims_severity_v3", "training_table", "ml_model", "train"),
        ("ml.claims_severity_v3", "app.pricing_engine", "ml_model", "application", "score"),
    ]
    for src, tgt, st, tt, xf in edges:
        platform.lineage.append(
            LineageEdge(
                edge_id=str(uuid4()),
                source_id=src,
                target_id=tgt,
                source_type=st,
                target_type=tt,
                transformation=xf,
            )
        )

    platform.features.extend(
        [
            FeatureDefinition(
                feature_id="feat_avg_incurred_12m",
                name="avg_incurred_12m",
                definition="Average incurred amount over trailing 12 months",
                source_tables=["ANALYTICS.CORE.fct_claims"],
                transformation="avg(incurred_amount) over 12m window",
                availability_timestamp_column="as_of_ts",
                owner="ml-platform",
                leakage_risk="low",
                performance_contribution=0.12,
                model_usage=["claims_severity_v3"],
            ),
            FeatureDefinition(
                feature_id="feat_days_to_report",
                name="days_to_report",
                definition="report_date - loss_date",
                source_tables=["ANALYTICS.CORE.fct_claims"],
                transformation="datediff(day, loss_date, report_date)",
                availability_timestamp_column="report_date",
                owner="ml-platform",
                leakage_risk="medium",
                performance_contribution=0.08,
                model_usage=["claims_severity_v3"],
            ),
            FeatureDefinition(
                feature_id="feat_ultimate_loss_ratio",
                name="ultimate_loss_ratio",
                definition="Closed claim ultimate / premium — POST OUTCOME",
                source_tables=["ANALYTICS.CORE.fct_claims"],
                transformation="ultimate / premium",
                availability_timestamp_column="close_date",
                owner="actuarial",
                leakage_risk="high",
                performance_contribution=0.35,
                model_usage=[],
            ),
        ]
    )
    platform.models.append(
        MLModel(
            model_id="ml.claims_severity_v3",
            name="claims_severity",
            version="3.2.1",
            stage="Production",
            framework="xgboost",
            features=["avg_incurred_12m", "days_to_report", "policy_risk_score"],
            training_table="ANALYTICS.ML.training_claims_model",
            target="severity_bucket",
            metrics={"auc": 0.81, "mae": 1200.0, "calibration_ece": 0.04, "auc_7d_ago": 0.84},
            deployed_at=now - timedelta(days=14),
            endpoint="local://claims-severity",
            mode="LOCAL_SIMULATION",
        )
    )
    platform.contracts.append(
        DataContract(
            contract_id="contract.claims.v2",
            dataset="RAW.CLAIM.claims",
            owner="claims-data-owners",
            schema_columns=_cols_for("claims"),
            freshness_sla_minutes=120,
            uniqueness_keys=["claim_id"],
            allowed_null_rates={"incurred_amount": 0.1, "paid_amount": 0.2},
            consumers=["model.analytics.stg_claims", "ml.claims_severity_v3"],
        )
    )

    task_names = [
        ("extract_claims", []),
        ("extract_policies", []),
        ("load_raw_claims", ["extract_claims"]),
        ("load_raw_policies", ["extract_policies"]),
        ("dbt_run_staging", ["load_raw_claims", "load_raw_policies"]),
        ("dbt_run_core", ["dbt_run_staging"]),
        ("dbt_test_core", ["dbt_run_core"]),
        ("feature_build", ["dbt_test_core"]),
        ("score_claims_model", ["feature_build"]),
    ]
    tasks: list[AirflowTask] = []
    for name, upstream in task_names:
        log = f"[{now.isoformat()}] Task {name} completed successfully\n"
        tasks.append(
            AirflowTask(
                task_id=name,
                dag_id="insurance_daily_pipeline",
                operator="PythonOperator" if "extract" in name or "score" in name else "BashOperator",
                status=PipelineStatus.SUCCESS,
                start_date=now - timedelta(hours=3),
                end_date=now - timedelta(hours=2),
                duration_seconds=rng.uniform(30, 900),
                upstream=upstream,
                log_excerpt=log,
            )
        )
        platform.task_logs[f"insurance_daily_pipeline.{name}"] = log
    by_id = {t.task_id: t for t in tasks}
    for t in tasks:
        for u in t.upstream:
            by_id[u].downstream.append(t.task_id)
    platform.dags.append(
        AirflowDag(
            dag_id="insurance_daily_pipeline",
            description="Daily insurance claims/policy analytics + ML scoring",
            schedule="0 6 * * *",
            owners=["data-platform"],
            tags=["insurance", "critical"],
            tasks=tasks,
            last_run_status=PipelineStatus.SUCCESS,
            last_run_at=now - timedelta(hours=2),
            next_run_at=now + timedelta(hours=4),
        )
    )

    warehouses = ["TRANSFORM_WH", "ANALYTICS_WH", "ML_WH"]
    for i in range(80):
        wh = rng.choice(warehouses)
        model = rng.choice(platform.dbt_models)
        bytes_scanned = int(model.estimated_bytes_scanned or 1e9) * rng.choice([1, 1, 1, 3, 8])
        elapsed = int(bytes_scanned / 5_000_000) + rng.randint(200, 20000)
        start = now - timedelta(hours=rng.randint(1, 168))
        status = "SUCCESS"
        err = None
        if i % 17 == 0:
            status = "FAILED"
            err = "Statement reached its timeout of 3600 second(s) and was canceled."
        platform.queries.append(
            QueryHistoryEntry(
                query_id=f"Q{i:05d}",
                warehouse=wh,
                user_name="dbt_service",
                database="ANALYTICS",
                schema_name=model.schema_name,
                query_text=f"select * from {model.name}",
                start_time=start,
                end_time=start + timedelta(milliseconds=elapsed),
                total_elapsed_ms=elapsed,
                bytes_scanned=bytes_scanned,
                rows_produced=rng.randint(1000, 5_000_000),
                credits_used=round(bytes_scanned / 1e12 * 2.5 + elapsed / 3_600_000, 4),
                status=status,
                error_message=err,
                dbt_model=model.unique_id,
            )
        )
    for h in range(48):
        for wh in warehouses:
            platform.warehouse_metrics.append(
                WarehouseMetric(
                    warehouse=wh,
                    timestamp=now - timedelta(hours=h),
                    credits=rng.uniform(0.5, 12.0),
                    queued_overload_time=rng.choice([0.0, 0.0, 0.0, 30.0, 120.0, 400.0]),
                    avg_running=rng.uniform(0, 8),
                    avg_queued=rng.uniform(0, 4),
                    size=rng.choice(["S", "M", "L", "XL"]),
                )
            )
            platform.cloudwatch_metrics.append(
                {
                    "namespace": "Airflow/DAG",
                    "metric": "TaskDuration",
                    "dag_id": "insurance_daily_pipeline",
                    "timestamp": (now - timedelta(hours=h)).isoformat(),
                    "value": rng.uniform(20, 1200),
                    "unit": "Seconds",
                }
            )

    for model in platform.dbt_models:
        if model.has_tests:
            platform.dbt_tests.append(
                DbtTestResult(
                    test_id=str(uuid4()),
                    test_name=f"unique_{model.name}_id",
                    model_unique_id=model.unique_id,
                    status="pass",
                    failures=0,
                    dimension=QualityDimension.UNIQUENESS,
                    executed_at=now - timedelta(hours=2),
                    column_name="id",
                )
            )

    for i in range(n_incidents):
        ftype = FAILURE_TYPES[i % len(FAILURE_TYPES)]
        incident, scenario, mutations = _make_failure(ftype, i, rng, now)
        platform.incidents.append(incident)
        platform.scenarios.append(scenario)
        if i < 10:
            _apply_mutations(platform, mutations)

    return platform


def _sample_sql(name: str, incremental: bool) -> str:
    if name == "fct_claims":
        return """
{{ config(materialized='incremental', unique_key='claim_id') }}
select
  c.claim_id as id,
  c.claim_id,
  c.policy_id,
  c.incurred_amount as amount,
  c.loss_date as event_date,
  current_timestamp() as updated_at
from {{ ref('stg_claims') }} c
left join {{ ref('dim_policy') }} p on c.policy_id = p.policy_id
{% if is_incremental() %}
where c.report_date > (select max(event_date) from {{ this }})
{% endif %}
""".strip()
    if name == "feat_policy_risk":
        return """
select
  p.policy_id as id,
  p.policy_id,
  count(c.claim_id) as claim_count,
  avg(c.amount) as avg_claim
from {{ ref('dim_policy') }} p
left join {{ ref('fct_claims') }} c on p.policy_id = c.policy_id
group by 1,2
""".strip()
    return f"select * from source_table -- {name} incremental={incremental}"
