from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from domain.enums import IncidentSeverity, PipelineStatus, QualityDimension


class ColumnSchema(BaseModel):
    name: str
    data_type: str
    nullable: bool = True
    is_primary_key: bool = False
    description: str | None = None
    enum_values: list[str] | None = None


class TableMetadata(BaseModel):
    table_id: str
    database: str
    schema_name: str
    table_name: str
    columns: list[ColumnSchema]
    row_count: int = 0
    bytes: int = 0
    last_altered: datetime | None = None
    owner: str = "data-platform"
    tags: list[str] = Field(default_factory=list)


class SchemaVersion(BaseModel):
    version_id: str
    table_id: str
    version: int
    columns: list[ColumnSchema]
    changed_at: datetime
    change_summary: str
    changed_by: str = "schema-registry"


class AirflowTask(BaseModel):
    task_id: str
    dag_id: str
    operator: str
    status: PipelineStatus
    start_date: datetime | None = None
    end_date: datetime | None = None
    duration_seconds: float | None = None
    try_number: int = 1
    max_tries: int = 3
    upstream: list[str] = Field(default_factory=list)
    downstream: list[str] = Field(default_factory=list)
    log_excerpt: str | None = None
    pool: str = "default_pool"
    queue: str = "default"


class AirflowDag(BaseModel):
    dag_id: str
    description: str
    schedule: str
    is_paused: bool = False
    owners: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    tasks: list[AirflowTask] = Field(default_factory=list)
    last_run_status: PipelineStatus = PipelineStatus.SUCCESS
    last_run_at: datetime | None = None
    next_run_at: datetime | None = None


class DbtModel(BaseModel):
    unique_id: str
    name: str
    schema_name: str
    materialization: str
    path: str
    depends_on: list[str] = Field(default_factory=list)
    columns: list[str] = Field(default_factory=list)
    has_tests: bool = False
    has_docs: bool = False
    is_incremental: bool = False
    sql_hash: str | None = None
    estimated_bytes_scanned: int | None = None


class DbtTestResult(BaseModel):
    test_id: str
    test_name: str
    model_unique_id: str
    status: str
    failures: int = 0
    dimension: QualityDimension | None = None
    message: str | None = None
    executed_at: datetime
    column_name: str | None = None


class QueryHistoryEntry(BaseModel):
    query_id: str
    warehouse: str
    user_name: str
    database: str
    schema_name: str
    query_text: str
    start_time: datetime
    end_time: datetime | None = None
    total_elapsed_ms: int = 0
    bytes_scanned: int = 0
    rows_produced: int = 0
    credits_used: float = 0.0
    status: str = "SUCCESS"
    error_message: str | None = None
    dbt_model: str | None = None


class WarehouseMetric(BaseModel):
    warehouse: str
    timestamp: datetime
    credits: float
    queued_overload_time: float = 0.0
    avg_running: float = 0.0
    avg_queued: float = 0.0
    size: str = "M"


class LineageEdge(BaseModel):
    edge_id: str
    source_id: str
    target_id: str
    source_type: str
    target_type: str
    transformation: str | None = None
    confidence: float = 1.0


class FeatureDefinition(BaseModel):
    feature_id: str
    name: str
    definition: str
    source_tables: list[str]
    transformation: str
    availability_timestamp_column: str
    owner: str
    version: int = 1
    leakage_risk: str = "unknown"
    performance_contribution: float | None = None
    model_usage: list[str] = Field(default_factory=list)


class MLModel(BaseModel):
    model_id: str
    name: str
    version: str
    stage: str
    framework: str
    features: list[str]
    training_table: str
    target: str
    metrics: dict[str, float] = Field(default_factory=dict)
    deployed_at: datetime | None = None
    endpoint: str | None = None
    mode: str = "LOCAL_SIMULATION"


class Incident(BaseModel):
    incident_id: str
    title: str
    severity: IncidentSeverity
    status: str
    source_system: str
    detected_at: datetime
    root_cause: str | None = None
    ground_truth_root_cause: str | None = None
    affected_assets: list[str] = Field(default_factory=list)
    summary: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class DataContract(BaseModel):
    contract_id: str
    dataset: str
    owner: str
    schema_columns: list[ColumnSchema]
    freshness_sla_minutes: int = 60
    uniqueness_keys: list[str] = Field(default_factory=list)
    allowed_null_rates: dict[str, float] = Field(default_factory=dict)
    version: int = 1
    consumers: list[str] = Field(default_factory=list)
