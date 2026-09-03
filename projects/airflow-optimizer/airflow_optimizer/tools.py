from __future__ import annotations

from typing import Any

import networkx as nx

from domain.enums import ActionRisk, PipelineStatus
from pydantic import BaseModel, Field
from tool_sdk.base import BaseTool, ToolContext, ToolError


class DagRefInput(BaseModel):
    dag_id: str


class TaskNode(BaseModel):
    task_id: str
    operator: str
    status: str
    duration_seconds: float | None = None
    upstream: list[str] = Field(default_factory=list)
    downstream: list[str] = Field(default_factory=list)


class DagGraphOutput(BaseModel):
    dag_id: str
    tasks: list[TaskNode]
    edge_count: int
    max_depth: int


class CriticalPathOutput(BaseModel):
    dag_id: str
    critical_path: list[str]
    total_duration_seconds: float
    bottleneck_task: str


class TaskDurationStat(BaseModel):
    task_id: str
    duration_seconds: float
    pct_of_critical_path: float
    status: str


class AnalyzeTaskDurationsOutput(BaseModel):
    dag_id: str
    tasks: list[TaskDurationStat]
    total_duration_seconds: float


class Bottleneck(BaseModel):
    task_id: str
    reason: str
    duration_seconds: float
    failure_rate: float


class FindBottlenecksOutput(BaseModel):
    dag_id: str
    bottlenecks: list[Bottleneck]


class DagRecommendation(BaseModel):
    type: str
    task_ids: list[str]
    rationale: str
    estimated_savings_seconds: float | None = None


class RecommendDagChangesOutput(BaseModel):
    dag_id: str
    recommendations: list[DagRecommendation]


class ApplyDagChangeInput(BaseModel):
    dag_id: str
    change_type: str
    task_ids: list[str]
    params: dict[str, Any] = Field(default_factory=dict)


class ApplyDagChangeOutput(BaseModel):
    dag_id: str
    change_type: str
    status: str
    message: str
    applied: bool


def _get_dag(store: Any, dag_id: str) -> Any:
    platform = store.require()
    dag = next((d for d in platform.dags if d.dag_id == dag_id), None)
    if not dag:
        raise ToolError(f"DAG not found: {dag_id}", code="NOT_FOUND")
    return dag


def _build_nx_graph(dag: Any) -> nx.DiGraph:
    g = nx.DiGraph()
    for t in dag.tasks:
        g.add_node(t.task_id, duration=t.duration_seconds or 0.0, status=t.status.value)
        for u in t.upstream:
            g.add_edge(u, t.task_id)
    return g


def build_airflow_opt_tools(store: Any) -> list[BaseTool[Any, Any]]:
    class GetDagGraph(BaseTool[DagRefInput, DagGraphOutput]):
        name = "get_dag_graph"
        description = "Get DAG task graph with dependencies"
        risk = ActionRisk.READ_ONLY
        input_model = DagRefInput
        output_model = DagGraphOutput

        def _execute(self, args: DagRefInput, context: ToolContext) -> DagGraphOutput:
            dag = _get_dag(store, args.dag_id)
            g = _build_nx_graph(dag)
            depths = {}
            for node in nx.topological_sort(g):
                preds = list(g.predecessors(node))
                depths[node] = max((depths[p] for p in preds), default=-1) + 1
            max_depth = max(depths.values()) if depths else 0
            tasks = [
                TaskNode(
                    task_id=t.task_id,
                    operator=t.operator,
                    status=t.status.value,
                    duration_seconds=t.duration_seconds,
                    upstream=t.upstream,
                    downstream=t.downstream,
                )
                for t in dag.tasks
            ]
            return DagGraphOutput(
                dag_id=args.dag_id,
                tasks=tasks,
                edge_count=g.number_of_edges(),
                max_depth=max_depth,
            )

    class ComputeCriticalPath(BaseTool[DagRefInput, CriticalPathOutput]):
        name = "compute_critical_path"
        description = "Compute critical path through DAG"
        risk = ActionRisk.READ_ONLY
        input_model = DagRefInput
        output_model = CriticalPathOutput

        def _execute(self, args: DagRefInput, context: ToolContext) -> CriticalPathOutput:
            dag = _get_dag(store, args.dag_id)
            g = _build_nx_graph(dag)
            # Longest path in DAG (critical path)
            path_lengths: dict[str, tuple[float, list[str]]] = {}
            for node in nx.topological_sort(g):
                dur = g.nodes[node].get("duration", 0.0)
                preds = list(g.predecessors(node))
                if not preds:
                    path_lengths[node] = (dur, [node])
                else:
                    best_pred = max(preds, key=lambda p: path_lengths[p][0])
                    plen, ppath = path_lengths[best_pred]
                    path_lengths[node] = (plen + dur, ppath + [node])
            if not path_lengths:
                return CriticalPathOutput(
                    dag_id=args.dag_id,
                    critical_path=[],
                    total_duration_seconds=0.0,
                    bottleneck_task="",
                )
            end_node = max(path_lengths, key=lambda n: path_lengths[n][0])
            total, path = path_lengths[end_node]
            bottleneck = max(path, key=lambda n: g.nodes[n].get("duration", 0.0))
            return CriticalPathOutput(
                dag_id=args.dag_id,
                critical_path=path,
                total_duration_seconds=round(total, 1),
                bottleneck_task=bottleneck,
            )

    class AnalyzeTaskDurations(BaseTool[DagRefInput, AnalyzeTaskDurationsOutput]):
        name = "analyze_task_durations"
        description = "Analyze task duration statistics"
        risk = ActionRisk.READ_ONLY
        input_model = DagRefInput
        output_model = AnalyzeTaskDurationsOutput

        def _execute(self, args: DagRefInput, context: ToolContext) -> AnalyzeTaskDurationsOutput:
            cp = ComputeCriticalPath()
            cp_out = cp._execute(DagRefInput(dag_id=args.dag_id), context)
            dag = _get_dag(store, args.dag_id)
            total = cp_out.total_duration_seconds or 1.0
            stats = []
            for t in dag.tasks:
                dur = t.duration_seconds or 0.0
                stats.append(
                    TaskDurationStat(
                        task_id=t.task_id,
                        duration_seconds=round(dur, 1),
                        pct_of_critical_path=round(dur / total * 100, 1),
                        status=t.status.value,
                    )
                )
            stats.sort(key=lambda s: s.duration_seconds, reverse=True)
            return AnalyzeTaskDurationsOutput(
                dag_id=args.dag_id,
                tasks=stats,
                total_duration_seconds=cp_out.total_duration_seconds,
            )

    class FindBottlenecks(BaseTool[DagRefInput, FindBottlenecksOutput]):
        name = "find_bottlenecks"
        description = "Find bottleneck and high-failure tasks"
        risk = ActionRisk.READ_ONLY
        input_model = DagRefInput
        output_model = FindBottlenecksOutput

        def _execute(self, args: DagRefInput, context: ToolContext) -> FindBottlenecksOutput:
            dag = _get_dag(store, args.dag_id)
            cp = ComputeCriticalPath()
            cp_out = cp._execute(DagRefInput(dag_id=args.dag_id), context)
            avg_dur = sum(t.duration_seconds or 0 for t in dag.tasks) / max(len(dag.tasks), 1)
            bottlenecks: list[Bottleneck] = []
            for t in dag.tasks:
                dur = t.duration_seconds or 0.0
                reasons = []
                if t.task_id in cp_out.critical_path and dur > avg_dur * 1.5:
                    reasons.append("on critical path with above-average duration")
                if t.status == PipelineStatus.FAILED:
                    reasons.append("recent failure")
                if t.try_number > 1:
                    reasons.append("retries observed")
                if reasons:
                    bottlenecks.append(
                        Bottleneck(
                            task_id=t.task_id,
                            reason="; ".join(reasons),
                            duration_seconds=dur,
                            failure_rate=1.0 if t.status == PipelineStatus.FAILED else 0.0,
                        )
                    )
            bottlenecks.sort(key=lambda b: b.duration_seconds, reverse=True)
            return FindBottlenecksOutput(dag_id=args.dag_id, bottlenecks=bottlenecks)

    class RecommendDagChanges(BaseTool[DagRefInput, RecommendDagChangesOutput]):
        name = "recommend_dag_changes"
        description = "Recommend parallelization, scheduling, retry, and split/merge changes"
        risk = ActionRisk.READ_ONLY
        input_model = DagRefInput
        output_model = RecommendDagChangesOutput

        def _execute(self, args: DagRefInput, context: ToolContext) -> RecommendDagChangesOutput:
            dag = _get_dag(store, args.dag_id)
            recs: list[DagRecommendation] = []
            # Parallelize independent extracts
            extracts = [t for t in dag.tasks if "extract" in t.task_id]
            if len(extracts) >= 2:
                recs.append(
                    DagRecommendation(
                        type="parallelize",
                        task_ids=[t.task_id for t in extracts],
                        rationale="Independent extract tasks can run in parallel",
                        estimated_savings_seconds=max(t.duration_seconds or 0 for t in extracts),
                    )
                )
            # Reduce deps: feature_build waits on dbt_test_core only
            feature = next((t for t in dag.tasks if t.task_id == "feature_build"), None)
            if feature and len(feature.upstream) > 1:
                recs.append(
                    DagRecommendation(
                        type="reduce_deps",
                        task_ids=["feature_build"],
                        rationale="Trim non-essential upstream dependencies",
                        estimated_savings_seconds=60.0,
                    )
                )
            # Schedule heavy tasks off-peak
            heavy = sorted(dag.tasks, key=lambda t: t.duration_seconds or 0, reverse=True)[:2]
            if heavy:
                recs.append(
                    DagRecommendation(
                        type="schedule",
                        task_ids=[t.task_id for t in heavy],
                        rationale="Schedule longest tasks during off-peak warehouse hours",
                    )
                )
            # Retries for flaky tasks
            failed = [t for t in dag.tasks if t.status == PipelineStatus.FAILED]
            if failed:
                recs.append(
                    DagRecommendation(
                        type="retries",
                        task_ids=[t.task_id for t in failed],
                        rationale="Increase max_tries for recently failed tasks",
                    )
                )
            # Split merge for dbt_run_core
            core = next((t for t in dag.tasks if "dbt_run_core" in t.task_id), None)
            if core and (core.duration_seconds or 0) > 300:
                recs.append(
                    DagRecommendation(
                        type="split_merge",
                        task_ids=[core.task_id],
                        rationale="Split large dbt run into model groups",
                        estimated_savings_seconds=(core.duration_seconds or 0) * 0.2,
                    )
                )
            return RecommendDagChangesOutput(dag_id=args.dag_id, recommendations=recs)

    class ApplyDagChange(BaseTool[ApplyDagChangeInput, ApplyDagChangeOutput]):
        name = "apply_dag_change"
        description = "Apply DAG optimization change (requires approval)"
        risk = ActionRisk.APPROVAL_REQUIRED
        input_model = ApplyDagChangeInput
        output_model = ApplyDagChangeOutput

        def _execute(self, args: ApplyDagChangeInput, context: ToolContext) -> ApplyDagChangeOutput:
            dag = _get_dag(store, args.dag_id)
            if args.change_type == "parallelize":
                for tid in args.task_ids:
                    task = next((t for t in dag.tasks if t.task_id == tid), None)
                    if task:
                        task.pool = "parallel_pool"
            elif args.change_type == "retries":
                for tid in args.task_ids:
                    task = next((t for t in dag.tasks if t.task_id == tid), None)
                    if task:
                        task.max_tries = args.params.get("max_tries", 5)
            return ApplyDagChangeOutput(
                dag_id=args.dag_id,
                change_type=args.change_type,
                status="applied_local_simulation",
                message=f"Applied {args.change_type} to {args.task_ids} in LOCAL_SIMULATION",
                applied=True,
            )

        def _dry_run(self, args: ApplyDagChangeInput, context: ToolContext) -> ApplyDagChangeOutput:
            return ApplyDagChangeOutput(
                dag_id=args.dag_id,
                change_type=args.change_type,
                status="dry_run",
                message=f"Would apply {args.change_type} to {args.task_ids}",
                applied=False,
            )

    return [
        GetDagGraph(),
        ComputeCriticalPath(),
        AnalyzeTaskDurations(),
        FindBottlenecks(),
        RecommendDagChanges(),
        ApplyDagChange(),
    ]
