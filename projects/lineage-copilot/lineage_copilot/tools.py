from __future__ import annotations

from typing import Any

from domain.enums import ActionRisk
from pydantic import BaseModel, Field
from tool_sdk.base import BaseTool, ToolContext, ToolError


class NodeRefInput(BaseModel):
    node_id: str
    depth: int | None = None


class LineageNodeOutput(BaseModel):
    node_id: str
    nodes: list[dict[str, Any]]
    evidence: list[dict[str, Any]] = Field(default_factory=list)


class FeatureOriginInput(BaseModel):
    feature_name: str


class FeatureOriginOutput(BaseModel):
    feature_name: str
    feature_id: str | None = None
    origin_tables: list[str]
    transformation: str
    lineage_path: list[str]
    evidence: list[dict[str, Any]]


class TableRefInput(BaseModel):
    table_id: str


class ModelsUsingTableOutput(BaseModel):
    table_id: str
    models: list[dict[str, Any]]
    evidence: list[dict[str, Any]]


class ModelRefInput(BaseModel):
    model_id: str


class TablesUsedByModelOutput(BaseModel):
    model_id: str
    tables: list[str]
    features: list[str]
    evidence: list[dict[str, Any]]


class ExplainTransformationInput(BaseModel):
    source_id: str
    target_id: str


class ExplainTransformationOutput(BaseModel):
    source_id: str
    target_id: str
    transformation: str | None
    path: list[str]
    evidence: list[dict[str, Any]]


class IdentifyImpactInput(BaseModel):
    node_id: str


class ImpactGroup(BaseModel):
    node_type: str
    count: int
    nodes: list[dict[str, Any]]


class IdentifyImpactOutput(BaseModel):
    node_id: str
    downstream_by_type: dict[str, list[dict[str, Any]]]
    total_impacted: int
    evidence: list[dict[str, Any]]


def _lineage_edges_for(store: Any, source: str | None = None, target: str | None = None) -> list[dict[str, Any]]:
    platform = store.require()
    edges = []
    for e in platform.lineage:
        if source and e.source_id != source and e.target_id != source:
            continue
        if target and e.source_id != target and e.target_id != target:
            continue
        edges.append(e.model_dump(mode="json"))
    return edges


def _edge_evidence(store: Any, source: str, target: str) -> list[dict[str, Any]]:
    return [
        e
        for e in _lineage_edges_for(store)
        if e["source_id"] == source and e["target_id"] == target
    ]


def build_lineage_tools(store: Any) -> list[BaseTool[Any, Any]]:
    class FindUpstream(BaseTool[NodeRefInput, LineageNodeOutput]):
        name = "find_upstream"
        description = "Find upstream lineage nodes with graph evidence"
        risk = ActionRisk.READ_ONLY
        input_model = NodeRefInput
        output_model = LineageNodeOutput

        def _execute(self, args: NodeRefInput, context: ToolContext) -> LineageNodeOutput:
            nodes = store.lineage.upstream(args.node_id, depth=args.depth)
            if not nodes and args.node_id not in store.lineage.g:
                raise ToolError(f"Node not found: {args.node_id}", code="NOT_FOUND")
            evidence = _lineage_edges_for(store, target=args.node_id)
            return LineageNodeOutput(node_id=args.node_id, nodes=nodes, evidence=evidence)

    class FindDownstream(BaseTool[NodeRefInput, LineageNodeOutput]):
        name = "find_downstream"
        description = "Find downstream lineage nodes with graph evidence"
        risk = ActionRisk.READ_ONLY
        input_model = NodeRefInput
        output_model = LineageNodeOutput

        def _execute(self, args: NodeRefInput, context: ToolContext) -> LineageNodeOutput:
            nodes = store.lineage.downstream(args.node_id, depth=args.depth)
            if not nodes and args.node_id not in store.lineage.g:
                raise ToolError(f"Node not found: {args.node_id}", code="NOT_FOUND")
            evidence = _lineage_edges_for(store, source=args.node_id)
            return LineageNodeOutput(node_id=args.node_id, nodes=nodes, evidence=evidence)

    class FindFeatureOrigin(BaseTool[FeatureOriginInput, FeatureOriginOutput]):
        name = "find_feature_origin"
        description = "Trace feature origin through insurance domain lineage"
        risk = ActionRisk.READ_ONLY
        input_model = FeatureOriginInput
        output_model = FeatureOriginOutput

        def _execute(self, args: FeatureOriginInput, context: ToolContext) -> FeatureOriginOutput:
            platform = store.require()
            feat = next(
                (f for f in platform.features if f.name == args.feature_name or f.feature_id == args.feature_name),
                None,
            )
            if not feat:
                raise ToolError(f"Feature not found: {args.feature_name}", code="NOT_FOUND")
            path: list[str] = [feat.feature_id]
            origin_tables = list(feat.source_tables)
            for table in feat.source_tables:
                upstream = store.lineage.upstream(table)
                path.extend([n["id"] for n in upstream[:3]])
            evidence = []
            for table in feat.source_tables:
                evidence.extend(_lineage_edges_for(store, target=table))
            return FeatureOriginOutput(
                feature_name=feat.name,
                feature_id=feat.feature_id,
                origin_tables=origin_tables,
                transformation=feat.transformation,
                lineage_path=path,
                evidence=evidence,
            )

    class FindModelsUsingTable(BaseTool[TableRefInput, ModelsUsingTableOutput]):
        name = "find_models_using_table"
        description = "Find ML models that depend on a table via lineage graph"
        risk = ActionRisk.READ_ONLY
        input_model = TableRefInput
        output_model = ModelsUsingTableOutput

        def _execute(self, args: TableRefInput, context: ToolContext) -> ModelsUsingTableOutput:
            downstream = store.lineage.downstream(args.table_id)
            ml_nodes = [n for n in downstream if n.get("node_type") == "ml_model"]
            platform = store.require()
            models = []
            for n in ml_nodes:
                mid = n["id"]
                m = next((x for x in platform.models if x.model_id == mid), None)
                models.append(
                    {
                        "model_id": mid,
                        "name": m.name if m else n.get("name", mid),
                        "stage": m.stage if m else "unknown",
                    }
                )
            evidence = _lineage_edges_for(store, source=args.table_id)
            return ModelsUsingTableOutput(table_id=args.table_id, models=models, evidence=evidence)

    class FindTablesUsedByModel(BaseTool[ModelRefInput, TablesUsedByModelOutput]):
        name = "find_tables_used_by_model"
        description = "Find tables and features used by an ML model"
        risk = ActionRisk.READ_ONLY
        input_model = ModelRefInput
        output_model = TablesUsedByModelOutput

        def _execute(self, args: ModelRefInput, context: ToolContext) -> TablesUsedByModelOutput:
            platform = store.require()
            model = next((m for m in platform.models if m.model_id == args.model_id), None)
            if not model:
                raise ToolError(f"Model not found: {args.model_id}", code="NOT_FOUND")
            upstream = store.lineage.upstream(args.model_id)
            tables = [n["id"] for n in upstream if n.get("node_type") == "table"]
            training = model.training_table
            if training not in tables:
                tables.append(training)
            evidence = _lineage_edges_for(store, target=args.model_id)
            return TablesUsedByModelOutput(
                model_id=args.model_id,
                tables=tables,
                features=model.features,
                evidence=evidence,
            )

    class ExplainTransformation(BaseTool[ExplainTransformationInput, ExplainTransformationOutput]):
        name = "explain_transformation"
        description = "Explain transformation between two lineage nodes"
        risk = ActionRisk.READ_ONLY
        input_model = ExplainTransformationInput
        output_model = ExplainTransformationOutput

        def _execute(
            self, args: ExplainTransformationInput, context: ToolContext
        ) -> ExplainTransformationOutput:
            path = store.lineage.path(args.source_id, args.target_id)
            evidence = []
            transformation = None
            if store.lineage.g.has_edge(args.source_id, args.target_id):
                edge = store.lineage.g[args.source_id][args.target_id]
                transformation = edge.get("transformation")
                evidence = _edge_evidence(store, args.source_id, args.target_id)
            elif path and len(path) >= 2:
                for i in range(len(path) - 1):
                    evidence.extend(_edge_evidence(store, path[i], path[i + 1]))
                if store.lineage.g.has_edge(path[-2], path[-1]):
                    transformation = store.lineage.g[path[-2]][path[-1]].get("transformation")
            return ExplainTransformationOutput(
                source_id=args.source_id,
                target_id=args.target_id,
                transformation=transformation,
                path=path,
                evidence=evidence,
            )

    class IdentifyImpact(BaseTool[IdentifyImpactInput, IdentifyImpactOutput]):
        name = "identify_impact"
        description = "Identify downstream impact of a node change"
        risk = ActionRisk.READ_ONLY
        input_model = IdentifyImpactInput
        output_model = IdentifyImpactOutput

        def _execute(self, args: IdentifyImpactInput, context: ToolContext) -> IdentifyImpactOutput:
            grouped = store.lineage.impact(args.node_id)
            total = sum(len(v) for v in grouped.values())
            evidence = _lineage_edges_for(store, source=args.node_id)
            return IdentifyImpactOutput(
                node_id=args.node_id,
                downstream_by_type=grouped,
                total_impacted=total,
                evidence=evidence,
            )

    return [
        FindUpstream(),
        FindDownstream(),
        FindFeatureOrigin(),
        FindModelsUsingTable(),
        FindTablesUsedByModel(),
        ExplainTransformation(),
        IdentifyImpact(),
    ]
