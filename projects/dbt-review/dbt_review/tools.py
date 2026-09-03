from __future__ import annotations

from typing import Any

from domain.enums import ActionRisk
from pydantic import BaseModel, Field
from tool_sdk.base import BaseTool, ToolContext, ToolError

from dbt_review.checks import analyze_sql


class InspectPrFilesInput(BaseModel):
    pr_id: str = "PR-001"
    changed_files: list[str] = Field(default_factory=list)


class PrFileChange(BaseModel):
    path: str
    status: str
    model_unique_id: str | None = None


class InspectPrFilesOutput(BaseModel):
    pr_id: str
    files: list[PrFileChange]


class GetDbtManifestInput(BaseModel):
    model_unique_id: str | None = None


class GetDbtManifestOutput(BaseModel):
    models: list[dict[str, Any]]
    total: int


class GetModelSqlInput(BaseModel):
    model_unique_id: str


class GetModelSqlOutput(BaseModel):
    model_unique_id: str
    path: str
    sql: str
    line_count: int


class RunStaticChecksInput(BaseModel):
    model_unique_id: str


class ReviewFinding(BaseModel):
    severity: str
    category: str
    message: str
    file: str
    line: int | None = None
    evidence: str
    fix: str


class RunStaticChecksOutput(BaseModel):
    model_unique_id: str
    findings: list[ReviewFinding]


class RunDbtTestsInput(BaseModel):
    model_unique_id: str | None = None
    status: str | None = None


class RunDbtTestsOutput(BaseModel):
    tests: list[dict[str, Any]]
    failed_count: int
    passed_count: int


class GetLineageInput(BaseModel):
    model_unique_id: str


class GetLineageOutput(BaseModel):
    upstream: list[dict[str, Any]]
    downstream: list[dict[str, Any]]


class GetQueryCharacteristicsInput(BaseModel):
    model_unique_id: str
    limit: int = 10


class QueryCharacteristic(BaseModel):
    query_id: str
    bytes_scanned: int
    credits_used: float
    total_elapsed_ms: int
    status: str


class GetQueryCharacteristicsOutput(BaseModel):
    model_unique_id: str
    queries: list[QueryCharacteristic]
    avg_bytes_scanned: float
    avg_credits: float


class EstimateCostInput(BaseModel):
    model_unique_id: str


class EstimateCostOutput(BaseModel):
    model_unique_id: str
    estimated_bytes_scanned: int
    estimated_credits: float
    estimated_usd: float
    basis: str


def build_dbt_review_tools(store: Any) -> list[BaseTool[Any, Any]]:
    class InspectPrFiles(BaseTool[InspectPrFilesInput, InspectPrFilesOutput]):
        name = "inspect_pr_files"
        description = "Inspect changed files in a dbt PR"
        risk = ActionRisk.READ_ONLY
        input_model = InspectPrFilesInput
        output_model = InspectPrFilesOutput

        def _execute(self, args: InspectPrFilesInput, context: ToolContext) -> InspectPrFilesOutput:
            platform = store.require()
            if args.changed_files:
                paths = args.changed_files
            else:
                paths = [m.path for m in platform.dbt_models if m.name in {"fct_claims", "feat_policy_risk"}]
            files: list[PrFileChange] = []
            for path in paths:
                model = next((m for m in platform.dbt_models if m.path == path), None)
                files.append(
                    PrFileChange(
                        path=path,
                        status="modified",
                        model_unique_id=model.unique_id if model else None,
                    )
                )
            return InspectPrFilesOutput(pr_id=args.pr_id, files=files)

    class GetDbtManifest(BaseTool[GetDbtManifestInput, GetDbtManifestOutput]):
        name = "get_dbt_manifest"
        description = "Load dbt manifest metadata for models"
        risk = ActionRisk.READ_ONLY
        input_model = GetDbtManifestInput
        output_model = GetDbtManifestOutput

        def _execute(self, args: GetDbtManifestInput, context: ToolContext) -> GetDbtManifestOutput:
            models = store.require().dbt_models
            if args.model_unique_id:
                models = [m for m in models if m.unique_id == args.model_unique_id]
            payload = [m.model_dump(mode="json") for m in models]
            return GetDbtManifestOutput(models=payload, total=len(payload))

    class GetModelSql(BaseTool[GetModelSqlInput, GetModelSqlOutput]):
        name = "get_model_sql"
        description = "Fetch compiled SQL for a dbt model"
        risk = ActionRisk.READ_ONLY
        input_model = GetModelSqlInput
        output_model = GetModelSqlOutput

        def _execute(self, args: GetModelSqlInput, context: ToolContext) -> GetModelSqlOutput:
            platform = store.require()
            model = next((m for m in platform.dbt_models if m.unique_id == args.model_unique_id), None)
            if not model:
                raise ToolError(f"Model not found: {args.model_unique_id}", code="NOT_FOUND")
            sql = platform.dbt_sql.get(args.model_unique_id, f"-- missing SQL for {model.name}")
            return GetModelSqlOutput(
                model_unique_id=args.model_unique_id,
                path=model.path,
                sql=sql,
                line_count=len(sql.splitlines()),
            )

    class RunStaticChecks(BaseTool[RunStaticChecksInput, RunStaticChecksOutput]):
        name = "run_static_checks"
        description = "Run deterministic SQL static analysis checks"
        risk = ActionRisk.READ_ONLY
        input_model = RunStaticChecksInput
        output_model = RunStaticChecksOutput

        def _execute(self, args: RunStaticChecksInput, context: ToolContext) -> RunStaticChecksOutput:
            platform = store.require()
            model = next((m for m in platform.dbt_models if m.unique_id == args.model_unique_id), None)
            if not model:
                raise ToolError("Model not found", code="NOT_FOUND")
            sql = platform.dbt_sql.get(args.model_unique_id, "")
            raw = analyze_sql(sql, file_path=model.path, model_meta=model.model_dump())
            findings = [ReviewFinding(**f) for f in raw]
            return RunStaticChecksOutput(model_unique_id=args.model_unique_id, findings=findings)

    class RunDbtTests(BaseTool[RunDbtTestsInput, RunDbtTestsOutput]):
        name = "run_dbt_tests"
        description = "Fetch actual dbt test results from platform store"
        risk = ActionRisk.READ_ONLY
        input_model = RunDbtTestsInput
        output_model = RunDbtTestsOutput

        def _execute(self, args: RunDbtTestsInput, context: ToolContext) -> RunDbtTestsOutput:
            tests = store.require().dbt_tests
            if args.model_unique_id:
                tests = [t for t in tests if t.model_unique_id == args.model_unique_id]
            if args.status:
                tests = [t for t in tests if t.status == args.status]
            payload = [t.model_dump(mode="json") for t in tests]
            failed = sum(1 for t in tests if t.status == "fail")
            passed = sum(1 for t in tests if t.status == "pass")
            return RunDbtTestsOutput(tests=payload, failed_count=failed, passed_count=passed)

    class GetLineage(BaseTool[GetLineageInput, GetLineageOutput]):
        name = "get_lineage"
        description = "Get upstream/downstream lineage for a dbt model"
        risk = ActionRisk.READ_ONLY
        input_model = GetLineageInput
        output_model = GetLineageOutput

        def _execute(self, args: GetLineageInput, context: ToolContext) -> GetLineageOutput:
            return GetLineageOutput(
                upstream=store.lineage.upstream(args.model_unique_id),
                downstream=store.lineage.downstream(args.model_unique_id),
            )

    class GetQueryCharacteristics(BaseTool[GetQueryCharacteristicsInput, GetQueryCharacteristicsOutput]):
        name = "get_query_characteristics"
        description = "Summarize Snowflake query characteristics for a dbt model"
        risk = ActionRisk.READ_ONLY
        input_model = GetQueryCharacteristicsInput
        output_model = GetQueryCharacteristicsOutput

        def _execute(
            self, args: GetQueryCharacteristicsInput, context: ToolContext
        ) -> GetQueryCharacteristicsOutput:
            queries = [
                q
                for q in store.require().queries
                if q.dbt_model == args.model_unique_id and q.status == "SUCCESS"
            ]
            queries = sorted(queries, key=lambda q: q.bytes_scanned, reverse=True)[: args.limit]
            chars = [
                QueryCharacteristic(
                    query_id=q.query_id,
                    bytes_scanned=q.bytes_scanned,
                    credits_used=q.credits_used,
                    total_elapsed_ms=q.total_elapsed_ms,
                    status=q.status,
                )
                for q in queries
            ]
            avg_bytes = sum(c.bytes_scanned for c in chars) / len(chars) if chars else 0.0
            avg_credits = sum(c.credits_used for c in chars) / len(chars) if chars else 0.0
            return GetQueryCharacteristicsOutput(
                model_unique_id=args.model_unique_id,
                queries=chars,
                avg_bytes_scanned=avg_bytes,
                avg_credits=avg_credits,
            )

    class EstimateCost(BaseTool[EstimateCostInput, EstimateCostOutput]):
        name = "estimate_cost"
        description = "Estimate Snowflake cost for a dbt model run"
        risk = ActionRisk.READ_ONLY
        input_model = EstimateCostInput
        output_model = EstimateCostOutput

        def _execute(self, args: EstimateCostInput, context: ToolContext) -> EstimateCostOutput:
            platform = store.require()
            model = next((m for m in platform.dbt_models if m.unique_id == args.model_unique_id), None)
            if not model:
                raise ToolError("Model not found", code="NOT_FOUND")
            model_queries = [q for q in platform.queries if q.dbt_model == args.model_unique_id]
            if model_queries:
                avg_bytes = sum(q.bytes_scanned for q in model_queries) / len(model_queries)
                avg_credits = sum(q.credits_used for q in model_queries) / len(model_queries)
                basis = f"historical_avg_n={len(model_queries)}"
            else:
                avg_bytes = float(model.estimated_bytes_scanned or 1_000_000_000)
                avg_credits = avg_bytes / 1e12 * 2.5
                basis = "manifest_estimate"
            usd = avg_credits * 3.0
            return EstimateCostOutput(
                model_unique_id=args.model_unique_id,
                estimated_bytes_scanned=int(avg_bytes),
                estimated_credits=round(avg_credits, 4),
                estimated_usd=round(usd, 4),
                basis=basis,
            )

    return [
        InspectPrFiles(),
        GetDbtManifest(),
        GetModelSql(),
        RunStaticChecks(),
        RunDbtTests(),
        GetLineage(),
        GetQueryCharacteristics(),
        EstimateCost(),
    ]
