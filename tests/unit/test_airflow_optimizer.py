from tool_sdk.registry import ToolRegistry

from airflow_optimizer.agent import AirflowOptimizerAgent
from airflow_optimizer.tools import build_airflow_opt_tools


def test_build_airflow_opt_tools(store):
    tools = build_airflow_opt_tools(store)
    assert len(tools) == 6
    assert any(t.name == "compute_critical_path" for t in tools)


def test_critical_path(store):
    registry = ToolRegistry()
    for tool in build_airflow_opt_tools(store):
        registry.register(tool)
    result = registry.call(
        "compute_critical_path",
        {"dag_id": "insurance_daily_pipeline"},
        _ctx(),
    )
    assert result.success
    assert len(result.output.critical_path) >= 2
    assert result.output.total_duration_seconds > 0


def test_recommend_dag_changes(store):
    registry = ToolRegistry()
    for tool in build_airflow_opt_tools(store):
        registry.register(tool)
    result = registry.call(
        "recommend_dag_changes",
        {"dag_id": "insurance_daily_pipeline"},
        _ctx(),
    )
    assert result.success
    assert len(result.output.recommendations) >= 1
    types = {r.type for r in result.output.recommendations}
    assert "parallelize" in types or "schedule" in types


def test_airflow_optimizer_agent(store):
    registry = ToolRegistry()
    for tool in build_airflow_opt_tools(store):
        registry.register(tool)
    agent = AirflowOptimizerAgent(registry)
    execution = agent.run("Optimize DAG", context={"dag_id": "insurance_daily_pipeline"})
    assert execution.final_result["success"] is True
    assert execution.final_result["critical_path"]


def _ctx():
    from tool_sdk.base import ToolContext
    return ToolContext(execution_id="test", agent_name="airflow_optimizer")
