from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class Scenario(BaseModel):
    scenario_id: str
    agent: str
    title: str
    description: str
    failure_type: str
    ground_truth_root_cause: str
    expected_tools: list[str] = Field(default_factory=list)
    context: dict[str, Any] = Field(default_factory=dict)
    difficulty: str = "medium"


def load_scenarios(path: str | Path) -> list[Scenario]:
    p = Path(path)
    data = json.loads(p.read_text())
    if isinstance(data, dict) and "scenarios" in data:
        data = data["scenarios"]
    return [Scenario.model_validate(item) for item in data]
