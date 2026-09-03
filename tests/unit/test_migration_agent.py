from tool_sdk.registry import ToolRegistry

from migration_agent.agent import MigrationAgent
from migration_agent.tools import build_migration_tools


def test_build_migration_tools(store):
    tools = build_migration_tools(store)
    assert len(tools) == 9


def test_map_columns(store):
    registry = ToolRegistry()
    for tool in build_migration_tools(store):
        registry.register(tool)
    result = registry.call(
        "map_columns",
        {"legacy_table": "legacy.claims", "target_table": "RAW.CLAIM.claims"},
        _ctx(),
    )
    assert result.success
    assert len(result.output.mappings) >= 1


def test_validate_migration_requires_checks(store):
    registry = ToolRegistry()
    for tool in build_migration_tools(store):
        registry.register(tool)
    result = registry.call(
        "validate_migration",
        {"legacy_table": "legacy.claims", "target_table": "RAW.CLAIM.claims"},
        _ctx(),
    )
    assert result.success
    assert hasattr(result.output, "row_counts_match")
    assert hasattr(result.output, "null_rates_match")
    assert hasattr(result.output, "aggregates_match")
    assert hasattr(result.output, "distributions_match")


def test_migration_agent_run(store):
    registry = ToolRegistry()
    for tool in build_migration_tools(store):
        registry.register(tool)
    agent = MigrationAgent(registry)
    execution = agent.run(
        "Migrate claims",
        context={"legacy_table": "legacy.claims", "target_table": "RAW.CLAIM.claims"},
    )
    assert "validated" in execution.final_result
    assert execution.final_result["success"] == execution.final_result["validated"]


def _ctx():
    from tool_sdk.base import ToolContext
    return ToolContext(execution_id="test", agent_name="migration")
