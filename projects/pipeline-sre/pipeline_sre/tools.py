from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from domain.enums import ActionRisk
from pydantic import BaseModel, Field
from tool_sdk.base import BaseTool, ToolContext, ToolError


class DagStatusInput(BaseModel):
    dag_id: str


class DagStatusOutput(BaseModel):
    dag_id: str
    last_run_status: str
    is_paused: bool
    tasks: list[dict[str, Any]]
    failed_tasks: list[str]


class TaskLogsInput(BaseModel):
    dag_id: str
    task_id: str


class TaskLogsOutput(BaseModel):
    dag_id: str
    task_id: str
    log: str
    status: str | None = None


class DbtRunInput(BaseModel):
    model_unique_id: str | None = None


class DbtRunOutput(BaseModel):
    models: list[dict[str, Any]]
    failed_signals: list[str] = Field(default_factory=list)


class DbtTestsInput(BaseModel):
    model_unique_id: str | None = None
    status: str | None = None


class DbtTestsOutput(BaseModel):
    tests: list[dict[str, Any]]
    failed_count: int


class DbtLineageInput(BaseModel):
    model_unique_id: str


class DbtLineageOutput(BaseModel):
    upstream: list[dict[str, Any]]
    downstream: list[dict[str, Any]]


class TableMetaInput(BaseModel):
    table_id: str


class TableMetaOutput(BaseModel):
    table: dict[str, Any]


class DataProfileInput(BaseModel):
    table_id: str


class DataProfileOutput(BaseModel):
    profile: dict[str, Any]


class SchemaHistoryInput(BaseModel):
    table_id: str


class SchemaHistoryOutput(BaseModel):
    versions: list[dict[str, Any]]


class QueryHistoryInput(BaseModel):
    dbt_model: str | None = None
    warehouse: str | None = None
    status: str | None = None
    limit: int = 20


class QueryHistoryOutput(BaseModel):
    queries: list[dict[str, Any]]


class CloudWatchInput(BaseModel):
    dag_id: str
    hours: int = 24


class CloudWatchOutput(BaseModel):
    metrics: list[dict[str, Any]]
    anomaly_hints: list[str] = Field(default_factory=list)


class CompareMetricsInput(BaseModel):
    table_id: str
    column: str


class CompareMetricsOutput(BaseModel):
    column: str
    current_null_rate: float
    historical_mean: float
    historical_std: float
    z_score: float
    is_anomaly: bool


class RestartTaskInput(BaseModel):
    dag_id: str
    task_id: str


class RestartTaskOutput(BaseModel):
    status: str
    message: str
    dag_id: str
    task_id: str


class RerunDbtInput(BaseModel):
    model_unique_id: str


class RerunDbtOutput(BaseModel):
    status: str
    message: str
    model_unique_id: str


class SafeSqlInput(BaseModel):
    sql: str


class SafeSqlOutput(BaseModel):
    status: str
    row_count: int = 0
    preview: list[dict[str, Any]] = Field(default_factory=list)
    message: str


class ValidatePipelineInput(BaseModel):
    dag_id: str


class ValidatePipelineOutput(BaseModel):
    healthy: bool
    failed_tasks: list[str]
    failed_tests: list[str]
    message: str


class IncidentReportInput(BaseModel):
    incident_id: str
    root_cause: str
    summary: str
    remediation: str
    evidence: list[str] = Field(default_factory=list)


class IncidentReportOutput(BaseModel):
    report_id: str
    path: str
    status: str


def build_pipeline_tools(store: Any) -> list[BaseTool[Any, Any]]:
    class GetAirflowDagStatus(BaseTool[DagStatusInput, DagStatusOutput]):
        name = "get_airflow_dag_status"
        description = "Get Airflow DAG run status and task states"
        risk = ActionRisk.READ_ONLY
        input_model = DagStatusInput
        output_model = DagStatusOutput

        def _execute(self, args: DagStatusInput, context: ToolContext) -> DagStatusOutput:
            platform = store.require()
            dag = next((d for d in platform.dags if d.dag_id == args.dag_id), None)
            if not dag:
                raise ToolError(f"DAG not found: {args.dag_id}", code="NOT_FOUND")
            tasks = [t.model_dump(mode="json") for t in dag.tasks]
            failed = [t.task_id for t in dag.tasks if t.status.value == "failed"]
            return DagStatusOutput(
                dag_id=dag.dag_id,
                last_run_status=dag.last_run_status.value,
                is_paused=dag.is_paused,
                tasks=tasks,
                failed_tasks=failed,
            )

    class GetTaskLogs(BaseTool[TaskLogsInput, TaskLogsOutput]):
        name = "get_task_logs"
        description = "Fetch Airflow task logs"
        risk = ActionRisk.READ_ONLY
        input_model = TaskLogsInput
        output_model = TaskLogsOutput

        def _execute(self, args: TaskLogsInput, context: ToolContext) -> TaskLogsOutput:
            platform = store.require()
            key = f"{args.dag_id}.{args.task_id}"
            log = platform.task_logs.get(key)
            if log is None:
                raise ToolError(f"Logs not found for {key}", code="NOT_FOUND")
            dag = next(d for d in platform.dags if d.dag_id == args.dag_id)
            task = next((t for t in dag.tasks if t.task_id == args.task_id), None)
            return TaskLogsOutput(
                dag_id=args.dag_id,
                task_id=args.task_id,
                log=log,
                status=task.status.value if task else None,
            )

    class GetDbtRun(BaseTool[DbtRunInput, DbtRunOutput]):
        name = "get_dbt_run"
        description = "Inspect dbt model run metadata"
        risk = ActionRisk.READ_ONLY
        input_model = DbtRunInput
        output_model = DbtRunOutput

        def _execute(self, args: DbtRunInput, context: ToolContext) -> DbtRunOutput:
            platform = store.require()
            models = platform.dbt_models
            if args.model_unique_id:
                models = [m for m in models if m.unique_id == args.model_unique_id]
            failed_signals = []
            for t in platform.dags[0].tasks:
                if t.status.value == "failed" and "dbt" in t.task_id:
                    failed_signals.append(t.task_id)
            return DbtRunOutput(
                models=[m.model_dump(mode="json") for m in models],
                failed_signals=failed_signals,
            )

    class GetDbtTests(BaseTool[DbtTestsInput, DbtTestsOutput]):
        name = "get_dbt_tests"
        description = "Fetch dbt test results"
        risk = ActionRisk.READ_ONLY
        input_model = DbtTestsInput
        output_model = DbtTestsOutput

        def _execute(self, args: DbtTestsInput, context: ToolContext) -> DbtTestsOutput:
            tests = store.require().dbt_tests
            if args.model_unique_id:
                tests = [t for t in tests if t.model_unique_id == args.model_unique_id]
            if args.status:
                tests = [t for t in tests if t.status == args.status]
            return DbtTestsOutput(
                tests=[t.model_dump(mode="json") for t in tests],
                failed_count=sum(1 for t in tests if t.status == "fail"),
            )

    class GetDbtLineage(BaseTool[DbtLineageInput, DbtLineageOutput]):
        name = "get_dbt_lineage"
        description = "Get upstream/downstream lineage for a dbt model"
        risk = ActionRisk.READ_ONLY
        input_model = DbtLineageInput
        output_model = DbtLineageOutput

        def _execute(self, args: DbtLineageInput, context: ToolContext) -> DbtLineageOutput:
            return DbtLineageOutput(
                upstream=store.lineage.upstream(args.model_unique_id),
                downstream=store.lineage.downstream(args.model_unique_id),
            )

    class GetTableMetadata(BaseTool[TableMetaInput, TableMetaOutput]):
        name = "get_table_metadata"
        description = "Get Snowflake table metadata"
        risk = ActionRisk.READ_ONLY
        input_model = TableMetaInput
        output_model = TableMetaOutput

        def _execute(self, args: TableMetaInput, context: ToolContext) -> TableMetaOutput:
            table = next((t for t in store.require().tables if t.table_id == args.table_id), None)
            if not table:
                raise ToolError(f"Table not found: {args.table_id}", code="NOT_FOUND")
            return TableMetaOutput(table=table.model_dump(mode="json"))

    class GetDataProfile(BaseTool[DataProfileInput, DataProfileOutput]):
        name = "get_data_profile"
        description = "Get data profile for a table"
        risk = ActionRisk.READ_ONLY
        input_model = DataProfileInput
        output_model = DataProfileOutput

        def _execute(self, args: DataProfileInput, context: ToolContext) -> DataProfileOutput:
            profile = store.require().data_profiles.get(args.table_id)
            if profile is None:
                raise ToolError(f"Profile not found: {args.table_id}", code="NOT_FOUND")
            return DataProfileOutput(profile=profile)

    class GetSchemaHistory(BaseTool[SchemaHistoryInput, SchemaHistoryOutput]):
        name = "get_schema_history"
        description = "Get schema version history"
        risk = ActionRisk.READ_ONLY
        input_model = SchemaHistoryInput
        output_model = SchemaHistoryOutput

        def _execute(self, args: SchemaHistoryInput, context: ToolContext) -> SchemaHistoryOutput:
            versions = [v for v in store.require().schema_versions if v.table_id == args.table_id]
            return SchemaHistoryOutput(versions=[v.model_dump(mode="json") for v in versions])

    class GetSnowflakeQueryHistory(BaseTool[QueryHistoryInput, QueryHistoryOutput]):
        name = "get_snowflake_query_history"
        description = "Inspect Snowflake query history"
        risk = ActionRisk.READ_ONLY
        input_model = QueryHistoryInput
        output_model = QueryHistoryOutput

        def _execute(self, args: QueryHistoryInput, context: ToolContext) -> QueryHistoryOutput:
            queries = store.require().queries
            if args.dbt_model:
                queries = [q for q in queries if q.dbt_model == args.dbt_model]
            if args.warehouse:
                queries = [q for q in queries if q.warehouse == args.warehouse]
            if args.status:
                queries = [q for q in queries if q.status == args.status]
            queries = sorted(queries, key=lambda q: q.start_time, reverse=True)[: args.limit]
            return QueryHistoryOutput(queries=[q.model_dump(mode="json") for q in queries])

    class GetCloudWatchMetrics(BaseTool[CloudWatchInput, CloudWatchOutput]):
        name = "get_cloudwatch_metrics"
        description = "Get CloudWatch-style pipeline metrics"
        risk = ActionRisk.READ_ONLY
        input_model = CloudWatchInput
        output_model = CloudWatchOutput

        def _execute(self, args: CloudWatchInput, context: ToolContext) -> CloudWatchOutput:
            metrics = [
                m
                for m in store.require().cloudwatch_metrics
                if m.get("dag_id") == args.dag_id
            ][: args.hours]
            hints = []
            values = [float(m["value"]) for m in metrics]
            if values and max(values) > (sum(values) / len(values)) * 2.5:
                hints.append("Task duration spike detected vs recent average")
            return CloudWatchOutput(metrics=metrics, anomaly_hints=hints)

    class CompareHistoricalMetrics(BaseTool[CompareMetricsInput, CompareMetricsOutput]):
        name = "compare_historical_metrics"
        description = "Compare current null rate vs historical distribution"
        risk = ActionRisk.READ_ONLY
        input_model = CompareMetricsInput
        output_model = CompareMetricsOutput

        def _execute(self, args: CompareMetricsInput, context: ToolContext) -> CompareMetricsOutput:
            import statistics

            profile = store.require().data_profiles.get(args.table_id)
            if not profile:
                raise ToolError("profile missing", code="NOT_FOUND")
            current = float(profile["null_rates"].get(args.column, 0.0))
            hist = [float(x) for x in profile.get("historical_null_rates", {}).get(args.column, [0.0])]
            mean = statistics.fmean(hist) if hist else 0.0
            std = statistics.pstdev(hist) if len(hist) > 1 else 0.01
            z = (current - mean) / (std or 0.01)
            return CompareMetricsOutput(
                column=args.column,
                current_null_rate=current,
                historical_mean=mean,
                historical_std=std,
                z_score=z,
                is_anomaly=abs(z) > 3,
            )

    class RestartTask(BaseTool[RestartTaskInput, RestartTaskOutput]):
        name = "restart_task"
        description = "Restart a failed Airflow task (requires approval)"
        risk = ActionRisk.APPROVAL_REQUIRED
        input_model = RestartTaskInput
        output_model = RestartTaskOutput

        def _execute(self, args: RestartTaskInput, context: ToolContext) -> RestartTaskOutput:
            platform = store.require()
            dag = next((d for d in platform.dags if d.dag_id == args.dag_id), None)
            if not dag:
                raise ToolError("DAG not found", code="NOT_FOUND")
            task = next((t for t in dag.tasks if t.task_id == args.task_id), None)
            if not task:
                raise ToolError("Task not found", code="NOT_FOUND")
            from domain.enums import PipelineStatus

            task.status = PipelineStatus.SUCCESS
            task.log_excerpt = f"[{datetime.now(timezone.utc).isoformat()}] Restarted and succeeded\n"
            platform.task_logs[f"{args.dag_id}.{args.task_id}"] = task.log_excerpt
            if all(t.status != PipelineStatus.FAILED for t in dag.tasks):
                dag.last_run_status = PipelineStatus.SUCCESS
            return RestartTaskOutput(
                status="success",
                message=f"Restarted {args.task_id}",
                dag_id=args.dag_id,
                task_id=args.task_id,
            )

        def _dry_run(self, args: RestartTaskInput, context: ToolContext) -> RestartTaskOutput:
            return RestartTaskOutput(
                status="dry_run",
                message=f"Would restart {args.task_id}",
                dag_id=args.dag_id,
                task_id=args.task_id,
            )

    class RerunDbtModel(BaseTool[RerunDbtInput, RerunDbtOutput]):
        name = "rerun_dbt_model"
        description = "Rerun a dbt model (safe automation after approval for prod)"
        risk = ActionRisk.APPROVAL_REQUIRED
        input_model = RerunDbtInput
        output_model = RerunDbtOutput

        def _execute(self, args: RerunDbtInput, context: ToolContext) -> RerunDbtOutput:
            model = next(
                (m for m in store.require().dbt_models if m.unique_id == args.model_unique_id),
                None,
            )
            if not model:
                raise ToolError("Model not found", code="NOT_FOUND")
            return RerunDbtOutput(
                status="success",
                message=f"Re-ran {model.name} in LOCAL_SIMULATION",
                model_unique_id=args.model_unique_id,
            )

        def _dry_run(self, args: RerunDbtInput, context: ToolContext) -> RerunDbtOutput:
            return RerunDbtOutput(
                status="dry_run",
                message=f"Would rerun {args.model_unique_id}",
                model_unique_id=args.model_unique_id,
            )

    class ExecuteSafeSql(BaseTool[SafeSqlInput, SafeSqlOutput]):
        name = "execute_safe_sql"
        description = "Execute allowlisted read-only SQL against local simulation"
        risk = ActionRisk.READ_ONLY
        input_model = SafeSqlInput
        output_model = SafeSqlOutput

        def _execute(self, args: SafeSqlInput, context: ToolContext) -> SafeSqlOutput:
            from tool_sdk.safety import SafetyPolicy

            SafetyPolicy().assert_sql_allowed(args.sql)
            # Local simulation: return profile-backed preview, never arbitrary execution
            return SafeSqlOutput(
                status="success",
                row_count=10,
                preview=[{"note": "LOCAL_SIMULATION", "sql": args.sql[:120]}],
                message="Read-only SQL accepted by allowlist; results simulated",
            )

    class ValidatePipeline(BaseTool[ValidatePipelineInput, ValidatePipelineOutput]):
        name = "validate_pipeline"
        description = "Validate DAG health and failing tests"
        risk = ActionRisk.SAFE_AUTOMATION
        input_model = ValidatePipelineInput
        output_model = ValidatePipelineOutput

        def _execute(self, args: ValidatePipelineInput, context: ToolContext) -> ValidatePipelineOutput:
            platform = store.require()
            dag = next((d for d in platform.dags if d.dag_id == args.dag_id), None)
            if not dag:
                raise ToolError("DAG not found", code="NOT_FOUND")
            failed_tasks = [t.task_id for t in dag.tasks if t.status.value == "failed"]
            failed_tests = [t.test_name for t in platform.dbt_tests if t.status == "fail"]
            healthy = not failed_tasks and not failed_tests
            return ValidatePipelineOutput(
                healthy=healthy,
                failed_tasks=failed_tasks,
                failed_tests=failed_tests,
                message="healthy" if healthy else "issues remain",
            )

    class CreateIncidentReport(BaseTool[IncidentReportInput, IncidentReportOutput]):
        name = "create_incident_report"
        description = "Write an incident report"
        risk = ActionRisk.SAFE_AUTOMATION
        input_model = IncidentReportInput
        output_model = IncidentReportOutput

        def _execute(self, args: IncidentReportInput, context: ToolContext) -> IncidentReportOutput:
            from pathlib import Path

            report_id = f"RPT-{args.incident_id}"
            path = Path("data/synthetic/incident_reports")
            path.mkdir(parents=True, exist_ok=True)
            out = path / f"{report_id}.md"
            out.write_text(
                f"# Incident Report {report_id}\n\n"
                f"**Root cause:** {args.root_cause}\n\n"
                f"**Summary:** {args.summary}\n\n"
                f"**Remediation:** {args.remediation}\n\n"
                f"**Evidence:**\n" + "\n".join(f"- {e}" for e in args.evidence)
            )
            return IncidentReportOutput(report_id=report_id, path=str(out), status="written")

    return [
        GetAirflowDagStatus(),
        GetTaskLogs(),
        GetDbtRun(),
        GetDbtTests(),
        GetDbtLineage(),
        GetTableMetadata(),
        GetDataProfile(),
        GetSchemaHistory(),
        GetSnowflakeQueryHistory(),
        GetCloudWatchMetrics(),
        CompareHistoricalMetrics(),
        RestartTask(),
        RerunDbtModel(),
        ExecuteSafeSql(),
        ValidatePipeline(),
        CreateIncidentReport(),
    ]
