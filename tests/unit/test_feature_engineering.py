from feature_engineering_agent.agent import FeatureEngineeringAgent
from feature_engineering_agent.tools import build_feature_tools

from tests.unit.conftest import build_agent


def test_feature_engineering_list():
    agent, _ = build_agent(FeatureEngineeringAgent, build_feature_tools)
    res = agent.call_tool("list_features", {})
    assert res["success"]
    assert len(res["output"]["features"]) >= 1


def test_feature_engineering_agent_run():
    agent, _ = build_agent(FeatureEngineeringAgent, build_feature_tools)
    execution = agent.run(
        "Validate avg_incurred_12m feature",
        {"feature_id": "feat_avg_incurred_12m"},
    )
    assert execution.final_result["success"] is True
    assert execution.final_result.get("leakage") is not None
