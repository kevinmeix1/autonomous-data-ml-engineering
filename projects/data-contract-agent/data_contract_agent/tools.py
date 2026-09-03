from __future__ import annotations

from typing import Any

from domain.enums import ActionRisk
from pydantic import BaseModel, Field
from tool_sdk.base import BaseTool, ToolContext, ToolError


class ListContractsInput(BaseModel):
    dataset: str | None = None


class ListContractsOutput(BaseModel):
    contracts: list[dict[str, Any]]


class GetSchemaRegistryInput(BaseModel):
    table_id: str


class GetSchemaRegistryOutput(BaseModel):
    table_id: str
    current_columns: list[dict[str, Any]]
    versions: list[dict[str, Any]]


class AnalyzeSchemaChangeInput(BaseModel):
    table_id: str
    from_version: int | None = None
    to_version: int | None = None


class SchemaChange(BaseModel):
    change_type: str
    column: str
    detail: str


class AnalyzeSchemaChangeOutput(BaseModel):
    table_id: str
    changes: list[SchemaChange]
    breaking: bool


class LineageImpactInput(BaseModel):
    node_id: str


class LineageImpactOutput(BaseModel):
    node_id: str
    impacted: dict[str, list[dict[str, Any]]]
    total_downstream: int


class ConsumerImpactInput(BaseModel):
    table_id: str


class ConsumerImpactOutput(BaseModel):
    table_id: str
    dbt_models: list[str]
    features: list[str]
    ml_models: list[str]
    contracts: list[str]


class RiskAssessmentInput(BaseModel):
    table_id: str
    changes: list[SchemaChange] = Field(default_factory=list)


class RiskAssessmentOutput(BaseModel):
    risk_level: str
    score: float
    factors: list[str]


class RecommendActionInput(BaseModel):
    table_id: str
    risk_level: str


class RecommendActionOutput(BaseModel):
    recommendations: list[str]
    requires_approval: bool


class PublishContractInput(BaseModel):
    table_id: str
    risk_level: str
    changelog: str = ""


class PublishContractOutput(BaseModel):
    status: str
    contract_id: str
    version: int
    message: str
    mode: str = "LOCAL_SIMULATION"


def _schema_diff(old_cols: list[Any], new_cols: list[Any]) -> list[SchemaChange]:
    old = {c.name: c for c in old_cols}
    new = {c.name: c for c in new_cols}
    changes: list[SchemaChange] = []
    for name in set(old) - set(new):
        changes.append(SchemaChange(change_type="removed", column=name, detail="Column removed"))
    for name in set(new) - set(old):
        changes.append(SchemaChange(change_type="added", column=name, detail="Column added"))
    for name in set(old) & set(new):
        o, n = old[name], new[name]
        if o.data_type != n.data_type:
            changes.append(
                SchemaChange(
                    change_type="type_change",
                    column=name,
                    detail=f"{o.data_type} -> {n.data_type}",
                )
            )
        if o.nullable and not n.nullable:
            changes.append(
                SchemaChange(change_type="nullable_tightened", column=name, detail="nullable -> not null")
            )
        if o.enum_values != n.enum_values:
            changes.append(
                SchemaChange(
                    change_type="enum_change",
                    column=name,
                    detail=f"enum {o.enum_values} -> {n.enum_values}",
                )
            )
    return changes


def build_contract_tools(store: Any) -> list[BaseTool[Any, Any]]:
    class ListContracts(BaseTool[ListContractsInput, ListContractsOutput]):
        name = "list_contracts"
        description = "List data contracts from schema registry"
        risk = ActionRisk.READ_ONLY
        input_model = ListContractsInput
        output_model = ListContractsOutput

        def _execute(self, args: ListContractsInput, context: ToolContext) -> ListContractsOutput:
            contracts = store.require().contracts
            if args.dataset:
                contracts = [c for c in contracts if c.dataset == args.dataset]
            return ListContractsOutput(contracts=[c.model_dump(mode="json") for c in contracts])

    class GetSchemaRegistry(BaseTool[GetSchemaRegistryInput, GetSchemaRegistryOutput]):
        name = "get_schema_registry"
        description = "Fetch schema registry entries for a table"
        risk = ActionRisk.READ_ONLY
        input_model = GetSchemaRegistryInput
        output_model = GetSchemaRegistryOutput

        def _execute(self, args: GetSchemaRegistryInput, context: ToolContext) -> GetSchemaRegistryOutput:
            platform = store.require()
            table = next((t for t in platform.tables if t.table_id == args.table_id), None)
            if not table:
                raise ToolError("Table not found", code="NOT_FOUND")
            versions = [v for v in platform.schema_versions if v.table_id == args.table_id]
            versions.sort(key=lambda v: v.version)
            return GetSchemaRegistryOutput(
                table_id=args.table_id,
                current_columns=[c.model_dump(mode="json") for c in table.columns],
                versions=[v.model_dump(mode="json") for v in versions],
            )

    class AnalyzeSchemaChange(BaseTool[AnalyzeSchemaChangeInput, AnalyzeSchemaChangeOutput]):
        name = "analyze_schema_change"
        description = "Diff schema versions and detect breaking changes"
        risk = ActionRisk.READ_ONLY
        input_model = AnalyzeSchemaChangeInput
        output_model = AnalyzeSchemaChangeOutput

        def _execute(
            self, args: AnalyzeSchemaChangeInput, context: ToolContext
        ) -> AnalyzeSchemaChangeOutput:
            versions = [v for v in store.require().schema_versions if v.table_id == args.table_id]
            versions.sort(key=lambda v: v.version)
            if len(versions) < 2:
                return AnalyzeSchemaChangeOutput(table_id=args.table_id, changes=[], breaking=False)
            from_v = args.from_version or versions[-2].version
            to_v = args.to_version or versions[-1].version
            old = next(v for v in versions if v.version == from_v)
            new = next(v for v in versions if v.version == to_v)
            changes = _schema_diff(old.columns, new.columns)
            breaking = any(
                c.change_type in {"removed", "type_change", "nullable_tightened", "enum_change"}
                for c in changes
            )
            return AnalyzeSchemaChangeOutput(table_id=args.table_id, changes=changes, breaking=breaking)

    class LineageImpact(BaseTool[LineageImpactInput, LineageImpactOutput]):
        name = "lineage_impact"
        description = "Analyze downstream lineage impact"
        risk = ActionRisk.READ_ONLY
        input_model = LineageImpactInput
        output_model = LineageImpactOutput

        def _execute(self, args: LineageImpactInput, context: ToolContext) -> LineageImpactOutput:
            impacted = store.lineage.impact(args.node_id)
            total = sum(len(v) for v in impacted.values())
            return LineageImpactOutput(node_id=args.node_id, impacted=impacted, total_downstream=total)

    class ConsumerImpact(BaseTool[ConsumerImpactInput, ConsumerImpactOutput]):
        name = "consumer_impact"
        description = "Identify dbt models, features, and ML models affected"
        risk = ActionRisk.READ_ONLY
        input_model = ConsumerImpactInput
        output_model = ConsumerImpactOutput

        def _execute(self, args: ConsumerImpactInput, context: ToolContext) -> ConsumerImpactOutput:
            platform = store.require()
            downstream = store.lineage.downstream(args.table_id)
            dbt_models = [
                n["id"]
                for n in downstream
                if n.get("node_type") == "dbt_model" or str(n.get("id", "")).startswith("model.")
            ]
            features = [f.name for f in platform.features if args.table_id in f.source_tables]
            ml_models = [m.name for m in platform.models if args.table_id in m.training_table or features]
            contracts = [c.contract_id for c in platform.contracts if c.dataset == args.table_id]
            return ConsumerImpactOutput(
                table_id=args.table_id,
                dbt_models=dbt_models,
                features=features,
                ml_models=ml_models,
                contracts=contracts,
            )

    class RiskAssessment(BaseTool[RiskAssessmentInput, RiskAssessmentOutput]):
        name = "risk_assessment"
        description = "Score contract breakage risk from schema changes"
        risk = ActionRisk.READ_ONLY
        input_model = RiskAssessmentInput
        output_model = RiskAssessmentOutput

        def _execute(self, args: RiskAssessmentInput, context: ToolContext) -> RiskAssessmentOutput:
            score = 0.0
            factors: list[str] = []
            for ch in args.changes:
                if ch.change_type == "removed":
                    score += 0.4
                    factors.append(f"removed column {ch.column}")
                elif ch.change_type == "type_change":
                    score += 0.3
                    factors.append(f"type change on {ch.column}")
                elif ch.change_type == "enum_change":
                    score += 0.25
                    factors.append(f"enum change on {ch.column}")
                else:
                    score += 0.1
                    factors.append(f"{ch.change_type} on {ch.column}")
            impact = self._consumer_impact(args.table_id)
            if impact["dbt_models"]:
                score += 0.15
                factors.append(f"{len(impact['dbt_models'])} dbt models downstream")
            if impact["ml_models"]:
                score += 0.2
                factors.append(f"{len(impact['ml_models'])} ML models affected")
            score = min(score, 1.0)
            level = "CRITICAL" if score >= 0.7 else "HIGH" if score >= 0.4 else "MEDIUM" if score >= 0.2 else "LOW"
            return RiskAssessmentOutput(risk_level=level, score=round(score, 3), factors=factors)

        def _consumer_impact(self, table_id: str) -> dict[str, list[str]]:
            platform = store.require()
            downstream = store.lineage.downstream(table_id)
            dbt = [n["id"] for n in downstream if "model." in str(n.get("id", ""))]
            ml = [m.name for m in platform.models]
            return {"dbt_models": dbt, "ml_models": ml}

    class RecommendAction(BaseTool[RecommendActionInput, RecommendActionOutput]):
        name = "recommend_action"
        description = "Recommend contract governance actions"
        risk = ActionRisk.READ_ONLY
        input_model = RecommendActionInput
        output_model = RecommendActionOutput

        def _execute(self, args: RecommendActionInput, context: ToolContext) -> RecommendActionOutput:
            recs: list[str] = []
            requires = False
            if args.risk_level in {"CRITICAL", "HIGH"}:
                recs.append("Notify all contract consumers before deployment")
                recs.append("Run downstream dbt tests and ML validation")
                requires = True
            if args.risk_level == "CRITICAL":
                recs.append("Block merge until backward-compatible migration plan approved")
                requires = True
            else:
                recs.append("Update contract version and changelog")
                recs.append("Add schema tests for new/changed columns")
            return RecommendActionOutput(recommendations=recs, requires_approval=requires)

    class PublishContractVersion(BaseTool[PublishContractInput, PublishContractOutput]):
        name = "publish_contract_version"
        description = "Publish a new data-contract version (requires approval)"
        risk = ActionRisk.APPROVAL_REQUIRED
        input_model = PublishContractInput
        output_model = PublishContractOutput

        def _execute(self, args: PublishContractInput, context: ToolContext) -> PublishContractOutput:
            from pathlib import Path
            import json
            from datetime import datetime, timezone

            platform = store.require()
            contract = next((c for c in platform.contracts if c.dataset == args.table_id), None)
            if contract is None:
                raise ToolError(f"No contract for {args.table_id}", code="NOT_FOUND")
            contract.version += 1
            out_dir = Path("data/synthetic/contracts")
            out_dir.mkdir(parents=True, exist_ok=True)
            payload = {
                "contract_id": contract.contract_id,
                "dataset": contract.dataset,
                "version": contract.version,
                "risk_level": args.risk_level,
                "changelog": args.changelog,
                "published_at": datetime.now(timezone.utc).isoformat(),
                "mode": "LOCAL_SIMULATION",
            }
            (out_dir / f"{contract.contract_id.replace('.', '_')}_v{contract.version}.json").write_text(
                json.dumps(payload, indent=2)
            )
            return PublishContractOutput(
                status="published",
                contract_id=contract.contract_id,
                version=contract.version,
                message=f"Published contract {contract.contract_id} v{contract.version} in LOCAL_SIMULATION",
                mode="LOCAL_SIMULATION",
            )

        def _dry_run(self, args: PublishContractInput, context: ToolContext) -> PublishContractOutput:
            return PublishContractOutput(
                status="dry_run",
                contract_id="pending",
                version=0,
                message=f"Would publish contract for {args.table_id}",
                mode="LOCAL_SIMULATION",
            )

    return [
        ListContracts(),
        GetSchemaRegistry(),
        AnalyzeSchemaChange(),
        LineageImpact(),
        ConsumerImpact(),
        RiskAssessment(),
        RecommendAction(),
        PublishContractVersion(),
    ]
