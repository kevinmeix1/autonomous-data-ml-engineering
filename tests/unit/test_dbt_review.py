from dbt_review.agent import DbtReviewAgent
from dbt_review.tools import build_dbt_review_tools

from tests.unit.conftest import build_agent


def test_dbt_review_tools_against_store():
    agent, store = build_agent(DbtReviewAgent, build_dbt_review_tools)
    registry = agent.tools
    manifest = registry.call("get_dbt_manifest", {}, _ctx(agent))
    assert manifest.success
    assert manifest.output.total >= 1


def test_dbt_review_agent_run():
    agent, _ = build_agent(DbtReviewAgent, build_dbt_review_tools)
    execution = agent.run(
        "Review dbt PR for fct_claims",
        {"model_unique_id": "model.analytics.fct_claims", "pr_id": "PR-TEST-1"},
    )
    assert execution.final_result is not None
    assert execution.final_result["success"] is True
    assert "findings" in execution.final_result
    assert len(execution.tool_calls) >= 5


def _ctx(agent):
    from tool_sdk.base import ToolContext

    return ToolContext(
        execution_id=agent.execution.execution_id,
        agent_name=agent.name,
        actor="test",
    )
