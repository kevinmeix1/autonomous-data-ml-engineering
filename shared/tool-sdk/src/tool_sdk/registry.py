from __future__ import annotations

from typing import Any

from tool_sdk.base import BaseTool, ToolContext, ToolError, ToolResult


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, BaseTool[Any, Any]] = {}

    def register(self, tool: BaseTool[Any, Any]) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Tool already registered: {tool.name}")
        self._tools[tool.name] = tool

    def get(self, name: str) -> BaseTool[Any, Any]:
        if name not in self._tools:
            raise ToolError(f"Unknown tool: {name}", code="UNKNOWN_TOOL")
        return self._tools[name]

    def list_tools(self) -> list[dict[str, str]]:
        return [
            {
                "name": t.name,
                "description": t.description,
                "risk": t.risk.value,
            }
            for t in self._tools.values()
        ]

    def call(
        self,
        name: str,
        args: dict[str, Any],
        context: ToolContext,
    ) -> ToolResult[Any]:
        tool = self.get(name)
        return tool.run(args, context)

    def schemas(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for tool in self._tools.values():
            out.append(
                {
                    "name": tool.name,
                    "description": tool.description,
                    "risk": tool.risk.value,
                    "input_schema": tool.input_model.model_json_schema(),
                    "output_schema": tool.output_model.model_json_schema(),
                }
            )
        return out
