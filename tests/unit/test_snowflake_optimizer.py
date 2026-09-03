from snowflake_optimizer.agent import SnowflakeOptimizerAgent
from snowflake_optimizer.tools import build_cost_tools

from tests.unit.conftest import build_agent


def test_snowflake_optimizer_tools():
    agent, _ = build_agent(SnowflakeOptimizerAgent, build_cost_tools)
    res = agent.call_tool("list_expensive_queries", {"limit": 3})
    assert res["success"]
    assert len(res["output"]["queries"]) <= 3


def test_snowflake_optimizer_agent_run():
    agent, _ = build_agent(SnowflakeOptimizerAgent, build_cost_tools)
    execution = agent.run(
        "Reduce Snowflake spend",
        {"model_unique_id": "model.analytics.fct_claims"},
    )
    assert execution.final_result["success"] is True
    assert "recommendations" in execution.final_result
    assert execution.final_result.get("awaiting_approval") is True
