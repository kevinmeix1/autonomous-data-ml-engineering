"""Ensure project packages are importable at runtime."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_PROJECT_PATHS = [
    _ROOT / "projects" / "pipeline-sre",
    _ROOT / "projects" / "dbt-review",
    _ROOT / "projects" / "snowflake-optimizer",
    _ROOT / "projects" / "data-quality-agent",
    _ROOT / "projects" / "data-contract-agent",
    _ROOT / "projects" / "feature-engineering-agent",
    _ROOT / "projects" / "ml-doctor",
    _ROOT / "projects" / "retraining-agent",
    _ROOT / "projects" / "airflow-optimizer",
    _ROOT / "projects" / "lineage-copilot",
    _ROOT / "projects" / "migration-agent",
    _ROOT / "projects" / "engineering-os",
    _ROOT / "shared" / "agent-sdk" / "src",
    _ROOT / "shared" / "tool-sdk" / "src",
    _ROOT / "shared" / "domain" / "src",
    _ROOT / "shared" / "data-generation" / "src",
    _ROOT / "shared" / "graph" / "src",
    _ROOT / "shared" / "observability" / "src",
    _ROOT / "shared" / "retrieval" / "src",
    _ROOT / "shared" / "evaluation" / "src",
    _ROOT,
]


def ensure_paths() -> None:
    for p in _PROJECT_PATHS:
        s = str(p)
        if s not in sys.path:
            sys.path.insert(0, s)


ensure_paths()
