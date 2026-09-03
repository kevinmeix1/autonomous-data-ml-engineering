from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer

from evaluation.metrics import EvaluationReport, evaluate_execution
from evaluation.scenarios import load_scenarios

app = typer.Typer(help="Run agent evaluation suites")


@app.command()
def run(
    suite: Path = typer.Option(..., exists=True),
    output: Path = typer.Option(Path("data/eval_results.json")),
    isolated: bool = typer.Option(
        True,
        help="For pipeline_sre, mutate a fresh platform with only that scenario's failure",
    ),
    limit: int = typer.Option(0, help="Optional max scenarios (0 = all)"),
) -> None:
    """Evaluate agents against a scenario suite.

    Default isolated=True avoids stacked-mutation pollution for Pipeline SRE.
    """
    scenarios = load_scenarios(suite)
    if limit > 0:
        scenarios = scenarios[:limit]
    reports: list[dict[str, Any]] = []

    for scenario in scenarios:
        try:
            if isolated and scenario.agent == "pipeline_sre":
                execution = _run_pipeline_sre_isolated(scenario)
            else:
                execution = _run_agent(scenario.agent, scenario.description, scenario.context)
            report = evaluate_execution(
                execution,
                scenario_id=scenario.scenario_id,
                ground_truth_root_cause=scenario.ground_truth_root_cause,
                expected_tools=scenario.expected_tools,
            )
            reports.append(report.model_dump(mode="json"))
        except Exception as exc:  # noqa: BLE001
            reports.append(
                EvaluationReport(
                    scenario_id=scenario.scenario_id,
                    agent=scenario.agent,
                    task_success=False,
                    diagnostic_accuracy=0.0,
                    false_diagnosis=True,
                    tool_efficiency=0.0,
                    unnecessary_tool_calls=0,
                    remediation_success=False,
                    time_to_resolution_ms=0.0,
                    token_cost_usd=0.0,
                    latency_ms=0.0,
                    safety_violations=0,
                    grounding_score=0.0,
                    details={"error": str(exc)},
                ).model_dump(mode="json")
            )

    output.parent.mkdir(parents=True, exist_ok=True)
    summary = _summarize(reports)
    output.write_text(json.dumps({"summary": summary, "reports": reports}, indent=2))
    typer.echo(json.dumps(summary, indent=2))


def _run_agent(agent_name: str, objective: str, context: dict[str, Any]):
    from adme_platform.api.agent_factory import create_agent

    agent = create_agent(agent_name)
    return agent.run(objective, context)


def _run_pipeline_sre_isolated(scenario) -> Any:
    """Fresh platform + single failure mutation for credible diagnosis scoring."""
    from adme_platform.api.store import PlatformStore
    from data_generation.generator import _apply_mutations, generate_platform
    from pipeline_sre.agent import PipelineSREAgent
    from pipeline_sre.tools import build_pipeline_tools
    from tool_sdk.registry import ToolRegistry

    store = PlatformStore(data_dir=Path("data/eval_runs") / scenario.scenario_id)
    store.platform = generate_platform(seed=hash(scenario.scenario_id) % 10_000, n_incidents=0)
    _apply_mutations(store.platform, {"type": scenario.ground_truth_root_cause})
    store._build_lineage()

    registry = ToolRegistry()
    for tool in build_pipeline_tools(store):
        registry.register(tool)
    agent = PipelineSREAgent(registry)
    return agent.run(scenario.description, scenario.context)


def _summarize(reports: list[dict[str, Any]]) -> dict[str, Any]:
    n = max(1, len(reports))
    return {
        "n_scenarios": len(reports),
        "success_rate": sum(1 for r in reports if r["task_success"]) / n,
        "diagnosis_accuracy": sum(r["diagnostic_accuracy"] for r in reports) / n,
        "remediation_success": sum(1 for r in reports if r["remediation_success"]) / n,
        "avg_tool_calls": sum(r.get("details", {}).get("tool_calls", 0) for r in reports) / n,
        "avg_latency_ms": sum(r["latency_ms"] for r in reports) / n,
        "avg_cost_usd": sum(r["token_cost_usd"] for r in reports) / n,
        "safety_violations": sum(r["safety_violations"] for r in reports),
        "isolated": True,
    }


if __name__ == "__main__":
    app()
