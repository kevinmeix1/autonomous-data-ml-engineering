from __future__ import annotations

import re
from typing import Any

from domain.enums import FindingSeverity


def _finding(
    *,
    severity: FindingSeverity,
    category: str,
    message: str,
    file: str,
    line: int | None,
    evidence: str,
    fix: str,
) -> dict[str, Any]:
    return {
        "severity": severity.value,
        "category": category,
        "message": message,
        "file": file,
        "line": line,
        "evidence": evidence,
        "fix": fix,
    }


def analyze_sql(sql: str, *, file_path: str, model_meta: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Deterministic static checks over dbt SQL."""
    findings: list[dict[str, Any]] = []
    lines = sql.splitlines()
    lower = sql.lower()
    model_meta = model_meta or {}

    if re.search(r"select\s+\*", lower):
        idx = next((i + 1 for i, ln in enumerate(lines) if "select" in ln.lower() and "*" in ln), 1)
        findings.append(
            _finding(
                severity=FindingSeverity.MEDIUM,
                category="sql_style",
                message="SELECT * detected; prefer explicit column lists",
                file=file_path,
                line=idx,
                evidence=lines[idx - 1].strip() if idx <= len(lines) else "select *",
                fix="Replace SELECT * with explicit columns",
            )
        )

    if "cross join" in lower:
        idx = next((i + 1 for i, ln in enumerate(lines) if "cross join" in ln.lower()), 1)
        findings.append(
            _finding(
                severity=FindingSeverity.HIGH,
                category="fanout",
                message="CROSS JOIN may cause row explosion",
                file=file_path,
                line=idx,
                evidence=lines[idx - 1].strip(),
                fix="Add join predicate or aggregate before joining",
            )
        )

    join_count = len(re.findall(r"\bjoin\b", lower))
    group_by = "group by" in lower
    if join_count >= 2 and not group_by and "count(" in lower:
        findings.append(
            _finding(
                severity=FindingSeverity.HIGH,
                category="fanout",
                message="Multiple joins with COUNT() but no GROUP BY — possible fanout",
                file=file_path,
                line=None,
                evidence=f"joins={join_count}, group_by={group_by}",
                fix="Add GROUP BY on grain keys or use DISTINCT/subquery dedupe",
            )
        )

    if model_meta.get("is_incremental"):
        if "is_incremental()" not in lower:
            findings.append(
                _finding(
                    severity=FindingSeverity.CRITICAL,
                    category="incremental",
                    message="Incremental model missing is_incremental() guard",
                    file=file_path,
                    line=None,
                    evidence="materialization=incremental without {% if is_incremental() %}",
                    fix="Wrap filter in {% if is_incremental() %} ... {% endif %}",
                )
            )
        elif "max(" not in lower and ">" not in lower:
            findings.append(
                _finding(
                    severity=FindingSeverity.HIGH,
                    category="incremental",
                    message="Incremental model may full-scan without watermark filter",
                    file=file_path,
                    line=None,
                    evidence="is_incremental present but no max/watermark predicate found",
                    fix="Filter on updated_at/report_date > (select max(...))",
                )
            )

    leakage_patterns = [
        (r"\bclose_date\b", "close_date used before claim closure"),
        (r"\bultimate\b", "ultimate loss may leak post-outcome information"),
        (r"\bpaid_amount\b.*\bloss_date\b", "paid_amount relative to loss_date may leak"),
        (r"current_timestamp\(\).*loss_date", "current_timestamp compared to loss_date"),
    ]
    for pattern, msg in leakage_patterns:
        if re.search(pattern, lower, re.DOTALL):
            findings.append(
                _finding(
                    severity=FindingSeverity.CRITICAL,
                    category="leakage",
                    message=f"Potential target leakage: {msg}",
                    file=file_path,
                    line=None,
                    evidence=f"pattern={pattern}",
                    fix="Use point-in-time columns available at prediction time only",
                )
            )

    if re.search(r"=\s*null\b", lower):
        idx = next((i + 1 for i, ln in enumerate(lines) if re.search(r"=\s*null\b", ln.lower())), 1)
        findings.append(
            _finding(
                severity=FindingSeverity.MEDIUM,
                category="sql_bug",
                message="Use IS NULL instead of = NULL",
                file=file_path,
                line=idx,
                evidence=lines[idx - 1].strip() if idx <= len(lines) else "= NULL",
                fix="Replace `= NULL` with `IS NULL`",
            )
        )

    if not model_meta.get("has_tests"):
        findings.append(
            _finding(
                severity=FindingSeverity.HIGH,
                category="testing",
                message="Model has no dbt tests configured",
                file=file_path,
                line=None,
                evidence="has_tests=false in manifest",
                fix="Add uniqueness/not_null/relationship tests in schema.yml",
            )
        )

    if not model_meta.get("has_docs"):
        findings.append(
            _finding(
                severity=FindingSeverity.SUGGESTION,
                category="documentation",
                message="Model documentation missing",
                file=file_path,
                line=None,
                evidence="has_docs=false in manifest",
                fix="Add model + column descriptions in schema.yml",
            )
        )

    return findings
