"""Isolated-scenario benchmark for pipeline SRE (and peers).

Each scenario gets a fresh synthetic platform with only that failure injected,
so ground-truth evaluation is not polluted by stacked mutations.
"""

from __future__ import annotations

import json
from pathlib import Path

from adme_platform.bootstrap import ensure_paths

ensure_paths()

from adme_platform.api.store import PlatformStore
from data_generation.failure_injection import inject_failure
from data_generation.generator import generate_platform
from evaluation.metrics import evaluate_execution
from pipeline_sre.agent import PipelineSREAgent
from pipeline_sre.tools import build_pipeline_tools
from tool_sdk.registry import ToolRegistry

# Map ground-truth failure types to failure_injection keys where available
INJECT_MAP = {
    "duplicate_records": "inject_duplicates",
    "schema_change": "corrupt_schema",
    "upstream_failure": "break_dag",
    "snowflake_query_timeout": "break_dag",
    "warehouse_overload": "break_dag",
    "invalid_sql": "break_dbt_dependency",
    "downstream_dependency_failure": "break_dbt_dependency",
    "null_spike": "inject_duplicates",  # closest deterministic injector fallback
    "missing_partition": "break_dag",
    "data_freshness_failure": "break_dag",
}


def run_isolated_pipeline_benchmark(n: int = 20, seed: int = 42) -> dict:
    base = generate_platform(seed=seed, n_incidents=n)
    reports = []
    for i, scenario in enumerate(base.scenarios[:n]):
        store = PlatformStore(data_dir=Path(f"data/benchmark_runs/scn_{i}"))
        store.platform = generate_platform(seed=seed + 1000 + i, n_incidents=0)
        # Apply only this failure via mutation helpers from generator
        from data_generation.generator import _apply_mutations

        ftype = scenario["ground_truth_root_cause"]
        _apply_mutations(store.platform, {"type": ftype})
        store._build_lineage()

        reg = ToolRegistry()
        for t in build_pipeline_tools(store):
            reg.register(t)
        agent = PipelineSREAgent(reg)
        ex = agent.run(scenario["description"], scenario.get("context") or {})
        report = evaluate_execution(
            ex,
            scenario_id=scenario["scenario_id"],
            ground_truth_root_cause=scenario["ground_truth_root_cause"],
            expected_tools=scenario.get("expected_tools"),
        )
        reports.append(report.model_dump(mode="json"))

    n_ok = max(1, len(reports))
    summary = {
        "n": len(reports),
        "success_rate": sum(1 for r in reports if r["task_success"]) / n_ok,
        "diagnosis_accuracy": sum(r["diagnostic_accuracy"] for r in reports) / n_ok,
        "avg_tool_calls": sum(r.get("details", {}).get("tool_calls", 0) for r in reports) / n_ok,
        "safety_violations": sum(r["safety_violations"] for r in reports),
        "avg_latency_ms": sum(r["latency_ms"] for r in reports) / n_ok,
    }
    out = {"summary": summary, "reports": reports}
    Path("data/benchmark_isolated.json").write_text(json.dumps(out, indent=2))
    return out


if __name__ == "__main__":
    result = run_isolated_pipeline_benchmark(20)
    print(json.dumps(result["summary"], indent=2))
