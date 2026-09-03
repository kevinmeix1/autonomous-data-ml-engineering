from __future__ import annotations

from typing import Any

from agent_sdk.base import BaseAgent
from agent_sdk.state import AgentExecution, Finding
from domain.enums import AgentState, EvidenceKind, IncidentSeverity
from tool_sdk.registry import ToolRegistry


class MigrationAgent(BaseAgent):
    name = "migration"
    description = "Legacy to Snowflake migration with validation-gated success"

    def __init__(self, tools: ToolRegistry, **kwargs: Any) -> None:
        super().__init__(tools, **kwargs)

    def run(self, objective: str, context: dict[str, Any] | None = None) -> AgentExecution:
        context = context or {}
        self.execution = type(self.execution)(agent=self.name, objective=objective)
        legacy_table = context.get("legacy_table", "legacy.claims")
        target_table = context.get("target_table", "RAW.CLAIM.claims")

        self._set_state(AgentState.OBSERVING, f"Inspecting legacy schema for {legacy_table}")
        schema = self.call_tool("inspect_legacy_schema", {"legacy_table": legacy_table})
        if not schema.get("success"):
            self.execution.state = AgentState.FAILED
            return self.finalize({"success": False, "error": schema.get("error")})

        self._set_state(AgentState.INVESTIGATING, "Profiling and mapping columns")
        self.call_tool("profile_table", {"table_id": legacy_table.replace("legacy.", "RAW.")})
        self.call_tool("profile_table", {"table_id": target_table})
        mapping = self.call_tool(
            "map_columns",
            {"legacy_table": legacy_table, "target_table": target_table},
        )
        types = self.call_tool(
            "detect_type_incompatibilities",
            {"legacy_table": legacy_table, "target_table": target_table},
        )

        self._set_state(AgentState.REMEDIATING, "Generating dbt models and tests")
        self.call_tool("generate_dbt_models", {"target_table": target_table})
        self.call_tool("generate_tests", {"target_table": target_table})
        self.call_tool(
            "generate_reconciliation_sql",
            {"legacy_table": legacy_table, "target_table": target_table},
        )

        self._set_state(AgentState.VERIFYING, "Running reconciliation and validation")
        recon = self.call_tool(
            "run_reconciliation",
            {"legacy_table": legacy_table, "target_table": target_table},
        )
        validation = self.call_tool(
            "validate_migration",
            {"legacy_table": legacy_table, "target_table": target_table},
        )

        validated = validation.get("output", {}).get("validated", False)
        self.add_finding(
            Finding(
                title="Migration validation" + (" passed" if validated else " failed"),
                severity=IncidentSeverity.INFO if validated else IncidentSeverity.HIGH,
                kind=EvidenceKind.OBSERVED_FACT,
                explanation=validation.get("output", {}).get("message", ""),
            )
        )

        return self.finalize(
            {
                "success": validated,
                "validated": validated,
                "legacy_table": legacy_table,
                "target_table": target_table,
                "column_mappings": len(mapping.get("output", {}).get("mappings", [])),
                "type_issues": len(types.get("output", {}).get("issues", [])),
                "reconciliation_passed": recon.get("output", {}).get("all_passed", False),
                "validation": validation.get("output"),
            }
        )
