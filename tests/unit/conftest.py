from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_PATHS = [
    _ROOT,
    _ROOT / "shared/agent-sdk/src",
    _ROOT / "shared/tool-sdk/src",
    _ROOT / "shared/domain/src",
    _ROOT / "shared/data-generation/src",
    _ROOT / "shared/graph/src",
    _ROOT / "shared/observability/src",
    _ROOT / "shared/retrieval/src",
    _ROOT / "shared/evaluation/src",
    _ROOT / "projects/pipeline-sre",
    _ROOT / "projects/dbt-review",
    _ROOT / "projects/snowflake-optimizer",
    _ROOT / "projects/data-quality-agent",
    _ROOT / "projects/data-contract-agent",
    _ROOT / "projects/feature-engineering-agent",
    _ROOT / "projects/ml-doctor",
    _ROOT / "projects/retraining-agent",
    _ROOT / "projects/airflow-optimizer",
    _ROOT / "projects/lineage-copilot",
    _ROOT / "projects/migration-agent",
    _ROOT / "projects/engineering-os",
]
for p in _PATHS:
    s = str(p)
    if s not in sys.path:
        sys.path.insert(0, s)

from adme_platform.api.store import STORE, PlatformStore  # noqa: E402
from tool_sdk.registry import ToolRegistry  # noqa: E402


@pytest.fixture
def store(tmp_path):
    s = PlatformStore(data_dir=tmp_path / "synthetic")
    s.load_or_generate(seed=42)
    return s


def build_agent(agent_cls: Any, build_tools_fn: Any, store: Any = None):
    s = store or STORE
    s.load_or_generate(seed=42)
    registry = ToolRegistry()
    for tool in build_tools_fn(s):
        registry.register(tool)
    return agent_cls(registry), s
