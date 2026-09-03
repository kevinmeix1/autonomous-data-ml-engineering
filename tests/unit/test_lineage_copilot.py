from tool_sdk.registry import ToolRegistry

from lineage_copilot.agent import LineageCopilotAgent
from lineage_copilot.tools import build_lineage_tools


def test_build_lineage_tools(store):
    tools = build_lineage_tools(store)
    assert len(tools) == 7


def test_find_upstream_with_evidence(store):
    registry = ToolRegistry()
    for tool in build_lineage_tools(store):
        registry.register(tool)
    result = registry.call(
        "find_upstream",
        {"node_id": "model.analytics.fct_claims", "depth": 3},
        _ctx(),
    )
    assert result.success
    assert len(result.output.nodes) >= 1
    assert isinstance(result.output.evidence, list)


def test_find_models_using_table(store):
    registry = ToolRegistry()
    for tool in build_lineage_tools(store):
        registry.register(tool)
    result = registry.call(
        "find_models_using_table",
        {"table_id": "RAW.CLAIM.claims"},
        _ctx(),
    )
    assert result.success
    assert len(result.output.evidence) >= 1


def test_find_feature_origin(store):
    registry = ToolRegistry()
    for tool in build_lineage_tools(store):
        registry.register(tool)
    result = registry.call(
        "find_feature_origin",
        {"feature_name": "avg_incurred_12m"},
        _ctx(),
    )
    assert result.success
    assert "fct_claims" in result.output.origin_tables[0] or result.output.origin_tables


def test_lineage_copilot_agent(store):
    registry = ToolRegistry()
    for tool in build_lineage_tools(store):
        registry.register(tool)
    agent = LineageCopilotAgent(registry)
    execution = agent.run(
        "Trace claims lineage",
        context={"node_id": "RAW.CLAIM.claims"},
    )
    assert execution.final_result["success"] is True
    assert execution.final_result["lineage_evidence_cited"] >= 0


def _ctx():
    from tool_sdk.base import ToolContext
    return ToolContext(execution_id="test", agent_name="lineage_copilot")
