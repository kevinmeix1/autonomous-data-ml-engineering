from domain.enums import ActionRisk
from pydantic import BaseModel
from tool_sdk.base import BaseTool, ToolContext
from tool_sdk.registry import ToolRegistry
from tool_sdk.safety import SafetyPolicy


class In(BaseModel):
    x: int


class Out(BaseModel):
    y: int


class AddTool(BaseTool[In, Out]):
    name = "add"
    description = "add one"
    risk = ActionRisk.READ_ONLY
    input_model = In
    output_model = Out

    def _execute(self, args: In, context: ToolContext) -> Out:
        return Out(y=args.x + 1)


def test_tool_registry_and_typed_io():
    reg = ToolRegistry()
    reg.register(AddTool())
    result = reg.call("add", {"x": 2}, ToolContext(execution_id="e1", agent_name="t"))
    assert result.success
    assert result.output is not None
    assert result.output.y == 3


def test_sql_safety_blocks_destructive():
    policy = SafetyPolicy()
    assert policy.classify_sql("SELECT * FROM claims") == ActionRisk.READ_ONLY
    assert policy.classify_sql("DROP TABLE claims") == ActionRisk.PROHIBITED
