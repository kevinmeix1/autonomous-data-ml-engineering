from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from domain.enums import ActionRisk
from pydantic import BaseModel, Field
from tool_sdk.base import BaseTool, ToolContext, ToolError


class ListExpensiveQueriesInput(BaseModel):
    limit: int = 10
    warehouse: str | None = None


class ListExpensiveQueriesOutput(BaseModel):
    queries: list[dict[str, Any]]
    total_credits: float


class GetWarehouseUtilizationInput(BaseModel):
    warehouse: str | None = None
    hours: int = 24


class WarehouseUtilization(BaseModel):
    warehouse: str
    avg_credits: float
    max_queued_overload: float
    avg_running: float
    size: str


class GetWarehouseUtilizationOutput(BaseModel):
    warehouses: list[WarehouseUtilization]


class GetTableSizesInput(BaseModel):
    schema_filter: str | None = None
    limit: int = 20


class TableSize(BaseModel):
    table_id: str
    row_count: int
    bytes: int
    gb: float


class GetTableSizesOutput(BaseModel):
    tables: list[TableSize]


class GetDbtModelCostInput(BaseModel):
    model_unique_id: str


class GetDbtModelCostOutput(BaseModel):
    model_unique_id: str
    query_count: int
    total_credits: float
    total_bytes_scanned: int
    avg_elapsed_ms: float


class EstimateSavingsInput(BaseModel):
    optimization_type: str
    target: str
    params: dict[str, Any] = Field(default_factory=dict)


class EstimateSavingsOutput(BaseModel):
    optimization_type: str
    target: str
    predicted_savings_credits: float
    predicted_savings_usd: float
    predicted_savings_pct: float
    baseline_credits: float
    model_version: str = "v1-linear-bytes"


class ApplyOptimizationInput(BaseModel):
    optimization_type: str
    target: str
    params: dict[str, Any] = Field(default_factory=dict)


class ApplyOptimizationOutput(BaseModel):
    status: str
    optimization_id: str
    applied_at: str
    message: str


class MeasureImpactInput(BaseModel):
    optimization_id: str
    baseline_credits: float
    predicted_savings_credits: float


class MeasureImpactOutput(BaseModel):
    optimization_id: str
    actual_credits_after: float
    actual_savings_credits: float
    actual_savings_pct: float
    prediction_error_pct: float
    within_tolerance: bool


def _model_credits(platform: Any, model_unique_id: str) -> tuple[float, int, list[Any]]:
    queries = [q for q in platform.queries if q.dbt_model == model_unique_id]
    credits = sum(q.credits_used for q in queries)
    bytes_scanned = sum(q.bytes_scanned for q in queries)
    return credits, bytes_scanned, queries


def build_cost_tools(store: Any) -> list[BaseTool[Any, Any]]:
    applied: dict[str, dict[str, Any]] = {}

    class ListExpensiveQueries(BaseTool[ListExpensiveQueriesInput, ListExpensiveQueriesOutput]):
        name = "list_expensive_queries"
        description = "List most expensive Snowflake queries by credits"
        risk = ActionRisk.READ_ONLY
        input_model = ListExpensiveQueriesInput
        output_model = ListExpensiveQueriesOutput

        def _execute(self, args: ListExpensiveQueriesInput, context: ToolContext) -> ListExpensiveQueriesOutput:
            queries = store.require().queries
            if args.warehouse:
                queries = [q for q in queries if q.warehouse == args.warehouse]
            ranked = sorted(queries, key=lambda q: q.credits_used, reverse=True)[: args.limit]
            payload = [q.model_dump(mode="json") for q in ranked]
            total = sum(q.credits_used for q in ranked)
            return ListExpensiveQueriesOutput(queries=payload, total_credits=round(total, 4))

    class GetWarehouseUtilization(BaseTool[GetWarehouseUtilizationInput, GetWarehouseUtilizationOutput]):
        name = "get_warehouse_utilization"
        description = "Summarize warehouse credit and queue utilization"
        risk = ActionRisk.READ_ONLY
        input_model = GetWarehouseUtilizationInput
        output_model = GetWarehouseUtilizationOutput

        def _execute(
            self, args: GetWarehouseUtilizationInput, context: ToolContext
        ) -> GetWarehouseUtilizationOutput:
            metrics = store.require().warehouse_metrics
            if args.warehouse:
                metrics = [m for m in metrics if m.warehouse == args.warehouse]
            metrics = sorted(metrics, key=lambda m: m.timestamp, reverse=True)[: args.hours * 3]
            by_wh: dict[str, list[Any]] = {}
            for m in metrics:
                by_wh.setdefault(m.warehouse, []).append(m)
            rows: list[WarehouseUtilization] = []
            for wh, items in by_wh.items():
                rows.append(
                    WarehouseUtilization(
                        warehouse=wh,
                        avg_credits=sum(x.credits for x in items) / len(items),
                        max_queued_overload=max(x.queued_overload_time for x in items),
                        avg_running=sum(x.avg_running for x in items) / len(items),
                        size=items[0].size,
                    )
                )
            return GetWarehouseUtilizationOutput(warehouses=rows)

    class GetTableSizes(BaseTool[GetTableSizesInput, GetTableSizesOutput]):
        name = "get_table_sizes"
        description = "List largest tables by bytes"
        risk = ActionRisk.READ_ONLY
        input_model = GetTableSizesInput
        output_model = GetTableSizesOutput

        def _execute(self, args: GetTableSizesInput, context: ToolContext) -> GetTableSizesOutput:
            tables = store.require().tables
            if args.schema_filter:
                tables = [t for t in tables if args.schema_filter in t.schema_name]
            ranked = sorted(tables, key=lambda t: t.bytes, reverse=True)[: args.limit]
            return GetTableSizesOutput(
                tables=[
                    TableSize(
                        table_id=t.table_id,
                        row_count=t.row_count,
                        bytes=t.bytes,
                        gb=round(t.bytes / 1e9, 2),
                    )
                    for t in ranked
                ]
            )

    class GetDbtModelCost(BaseTool[GetDbtModelCostInput, GetDbtModelCostOutput]):
        name = "get_dbt_model_cost"
        description = "Aggregate Snowflake cost for a dbt model"
        risk = ActionRisk.READ_ONLY
        input_model = GetDbtModelCostInput
        output_model = GetDbtModelCostOutput

        def _execute(self, args: GetDbtModelCostInput, context: ToolContext) -> GetDbtModelCostOutput:
            platform = store.require()
            model = next((m for m in platform.dbt_models if m.unique_id == args.model_unique_id), None)
            if not model:
                raise ToolError("Model not found", code="NOT_FOUND")
            credits, bytes_scanned, queries = _model_credits(platform, args.model_unique_id)
            avg_ms = (
                sum(q.total_elapsed_ms for q in queries) / len(queries) if queries else 0.0
            )
            return GetDbtModelCostOutput(
                model_unique_id=args.model_unique_id,
                query_count=len(queries),
                total_credits=round(credits, 4),
                total_bytes_scanned=bytes_scanned,
                avg_elapsed_ms=avg_ms,
            )

    class EstimateSavings(BaseTool[EstimateSavingsInput, EstimateSavingsOutput]):
        name = "estimate_savings"
        description = "Estimate savings from a proposed optimization"
        risk = ActionRisk.READ_ONLY
        input_model = EstimateSavingsInput
        output_model = EstimateSavingsOutput

        def _execute(self, args: EstimateSavingsInput, context: ToolContext) -> EstimateSavingsOutput:
            platform = store.require()
            baseline = 0.0
            pct = 0.0
            if args.optimization_type == "cluster_key":
                table = next((t for t in platform.tables if t.table_id == args.target), None)
                baseline = (table.bytes / 1e12 * 2.5) if table else 1.0
                pct = float(args.params.get("expected_pct", 0.25))
            elif args.optimization_type == "warehouse_downsize":
                wh_metrics = [m for m in platform.warehouse_metrics if m.warehouse == args.target]
                baseline = sum(m.credits for m in wh_metrics[:24]) / max(len(wh_metrics[:24]), 1)
                pct = float(args.params.get("expected_pct", 0.35))
            elif args.optimization_type == "incremental_filter":
                credits, _, _ = _model_credits(platform, args.target)
                baseline = credits or 1.0
                pct = float(args.params.get("expected_pct", 0.4))
            else:
                baseline = float(args.params.get("baseline_credits", 1.0))
                pct = float(args.params.get("expected_pct", 0.15))
            savings = baseline * pct
            return EstimateSavingsOutput(
                optimization_type=args.optimization_type,
                target=args.target,
                predicted_savings_credits=round(savings, 4),
                predicted_savings_usd=round(savings * 3.0, 4),
                predicted_savings_pct=round(pct * 100, 2),
                baseline_credits=round(baseline, 4),
            )

    class ApplyOptimization(BaseTool[ApplyOptimizationInput, ApplyOptimizationOutput]):
        name = "apply_optimization"
        description = "Apply a cost optimization (requires approval)"
        risk = ActionRisk.APPROVAL_REQUIRED
        input_model = ApplyOptimizationInput
        output_model = ApplyOptimizationOutput

        def _execute(self, args: ApplyOptimizationInput, context: ToolContext) -> ApplyOptimizationOutput:
            opt_id = f"OPT-{args.optimization_type}-{args.target}".replace(".", "_")[:64]
            applied[opt_id] = {
                "type": args.optimization_type,
                "target": args.target,
                "params": args.params,
                "applied_at": datetime.now(timezone.utc).isoformat(),
            }
            return ApplyOptimizationOutput(
                status="applied",
                optimization_id=opt_id,
                applied_at=applied[opt_id]["applied_at"],
                message=f"Applied {args.optimization_type} on {args.target} in LOCAL_SIMULATION",
            )

        def _dry_run(self, args: ApplyOptimizationInput, context: ToolContext) -> ApplyOptimizationOutput:
            return ApplyOptimizationOutput(
                status="dry_run",
                optimization_id=f"DRY-{args.optimization_type}",
                applied_at=datetime.now(timezone.utc).isoformat(),
                message=f"Would apply {args.optimization_type} on {args.target}",
            )

    class MeasureImpact(BaseTool[MeasureImpactInput, MeasureImpactOutput]):
        name = "measure_impact"
        description = "Measure actual savings vs prediction after optimization"
        risk = ActionRisk.READ_ONLY
        input_model = MeasureImpactInput
        output_model = MeasureImpactOutput

        def _execute(self, args: MeasureImpactInput, context: ToolContext) -> MeasureImpactOutput:
            # Deterministic simulation: actual savings = 92% of predicted
            actual = args.predicted_savings_credits * 0.92
            baseline_after = max(args.baseline_credits - actual, 0.01)
            actual_pct = (actual / args.baseline_credits * 100) if args.baseline_credits else 0.0
            pred_pct = (
                args.predicted_savings_credits / args.baseline_credits * 100
                if args.baseline_credits
                else 0.0
            )
            error = abs(actual_pct - pred_pct)
            return MeasureImpactOutput(
                optimization_id=args.optimization_id,
                actual_credits_after=round(baseline_after, 4),
                actual_savings_credits=round(actual, 4),
                actual_savings_pct=round(actual_pct, 2),
                prediction_error_pct=round(error, 2),
                within_tolerance=error <= 15.0,
            )

    return [
        ListExpensiveQueries(),
        GetWarehouseUtilization(),
        GetTableSizes(),
        GetDbtModelCost(),
        EstimateSavings(),
        ApplyOptimization(),
        MeasureImpact(),
    ]
