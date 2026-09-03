from __future__ import annotations

from domain.enums import ActionRisk
from tool_sdk.base import ToolError


class SafetyPolicy:
    """Central allowlist / risk policy for tool execution."""

    PROHIBITED_PATTERNS = (
        "rm -rf",
        "drop table",
        "drop database",
        "truncate table",
        "delete from",
        ";--",
        "xp_cmdshell",
    )

    def __init__(self, *, allow_high_risk: bool = False, require_approval: bool = True):
        self.allow_high_risk = allow_high_risk
        self.require_approval = require_approval

    def classify_sql(self, sql: str) -> ActionRisk:
        lowered = sql.lower().strip()
        for pattern in self.PROHIBITED_PATTERNS:
            if pattern in lowered:
                return ActionRisk.PROHIBITED
        if lowered.startswith(("select", "show", "describe", "explain", "with")):
            # Still block multi-statement
            if ";" in lowered.rstrip(";"):
                return ActionRisk.PROHIBITED
            return ActionRisk.READ_ONLY
        if lowered.startswith(("create or replace view", "alter view")):
            return ActionRisk.APPROVAL_REQUIRED
        return ActionRisk.PROHIBITED

    def assert_sql_allowed(self, sql: str) -> None:
        risk = self.classify_sql(sql)
        if risk == ActionRisk.PROHIBITED:
            raise ToolError("SQL rejected by safety policy", code="SQL_PROHIBITED", details={"sql": sql[:200]})


def assert_allowed(risk: ActionRisk, *, approved: bool = False) -> None:
    if risk == ActionRisk.PROHIBITED:
        raise ToolError("Action is prohibited", code="PROHIBITED")
    if risk == ActionRisk.APPROVAL_REQUIRED and not approved:
        raise ToolError("Human approval required", code="APPROVAL_REQUIRED")
