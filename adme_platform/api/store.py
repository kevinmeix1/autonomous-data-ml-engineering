from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from data_generation.generator import SyntheticPlatform, generate_platform
from graph.lineage import LineageGraph
from observability.audit import AuditLog
from observability.tracker import ObservabilityStore
from retrieval.kb import KnowledgeBase


class PlatformStore:
    """In-memory platform state backed by synthetic data files."""

    def __init__(self, data_dir: str | Path = "data/synthetic") -> None:
        self.data_dir = Path(data_dir)
        self.platform: SyntheticPlatform | None = None
        self.lineage = LineageGraph()
        self.audit = AuditLog()
        self.obs = ObservabilityStore()
        self.kb = KnowledgeBase("knowledge-base")
        self.executions: dict[str, dict[str, Any]] = {}
        self.approvals: dict[str, dict[str, Any]] = {}

    def load_or_generate(self, seed: int = 42) -> SyntheticPlatform:
        platform_path = self.data_dir / "platform.json"
        if platform_path.exists():
            self.platform = SyntheticPlatform.model_validate_json(platform_path.read_text())
        else:
            self.platform = generate_platform(seed=seed)
            self.platform.to_files(self.data_dir)
        self._build_lineage()
        return self.platform

    def _build_lineage(self) -> None:
        assert self.platform is not None
        self.lineage = LineageGraph()
        for table in self.platform.tables:
            self.lineage.add_node(table.table_id, "table", name=table.table_name)
        for model in self.platform.dbt_models:
            self.lineage.add_node(model.unique_id, "dbt_model", name=model.name)
        for feat in self.platform.features:
            self.lineage.add_node(feat.feature_id, "feature", name=feat.name)
        for model in self.platform.models:
            self.lineage.add_node(model.model_id, "ml_model", name=model.name)
        self.lineage.add_node("app.pricing_engine", "application", name="pricing_engine")
        for edge in self.platform.lineage:
            if edge.source_id not in self.lineage.g:
                self.lineage.add_node(edge.source_id, edge.source_type)
            if edge.target_id not in self.lineage.g:
                self.lineage.add_node(edge.target_id, edge.target_type)
            self.lineage.add_edge(edge)

    def require(self) -> SyntheticPlatform:
        if self.platform is None:
            self.load_or_generate()
        assert self.platform is not None
        return self.platform

    def save_execution(self, execution: dict[str, Any]) -> None:
        self.executions[execution["execution_id"]] = execution
        path = self.data_dir / "executions"
        path.mkdir(parents=True, exist_ok=True)
        (path / f"{execution['execution_id']}.json").write_text(json.dumps(execution, indent=2, default=str))


STORE = PlatformStore()
