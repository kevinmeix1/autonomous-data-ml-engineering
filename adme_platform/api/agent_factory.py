from __future__ import annotations

from typing import Any

import adme_platform.bootstrap  # noqa: F401 — path setup
from agent_sdk.base import BaseAgent
from adme_platform.api.store import STORE
from tool_sdk.registry import ToolRegistry


def _pipeline_sre() -> BaseAgent:
    from pipeline_sre.agent import PipelineSREAgent
    from pipeline_sre.tools import build_pipeline_tools

    registry = ToolRegistry()
    for tool in build_pipeline_tools(STORE):
        registry.register(tool)
    return PipelineSREAgent(registry)


def _dbt_review() -> BaseAgent:
    from dbt_review.agent import DbtReviewAgent
    from dbt_review.tools import build_dbt_review_tools

    registry = ToolRegistry()
    for tool in build_dbt_review_tools(STORE):
        registry.register(tool)
    return DbtReviewAgent(registry)


def _snowflake_optimizer() -> BaseAgent:
    from snowflake_optimizer.agent import SnowflakeOptimizerAgent
    from snowflake_optimizer.tools import build_cost_tools

    registry = ToolRegistry()
    for tool in build_cost_tools(STORE):
        registry.register(tool)
    return SnowflakeOptimizerAgent(registry)


def _data_quality() -> BaseAgent:
    from data_quality_agent.agent import DataQualityAgent
    from data_quality_agent.tools import build_dq_tools

    registry = ToolRegistry()
    for tool in build_dq_tools(STORE):
        registry.register(tool)
    return DataQualityAgent(registry)


def _data_contract() -> BaseAgent:
    from data_contract_agent.agent import DataContractAgent
    from data_contract_agent.tools import build_contract_tools

    registry = ToolRegistry()
    for tool in build_contract_tools(STORE):
        registry.register(tool)
    return DataContractAgent(registry)


def _feature_engineering() -> BaseAgent:
    from feature_engineering_agent.agent import FeatureEngineeringAgent
    from feature_engineering_agent.tools import build_feature_tools

    registry = ToolRegistry()
    for tool in build_feature_tools(STORE):
        registry.register(tool)
    return FeatureEngineeringAgent(registry)


def _ml_doctor() -> BaseAgent:
    from ml_doctor.agent import MLDoctorAgent
    from ml_doctor.tools import build_ml_doctor_tools

    registry = ToolRegistry()
    for tool in build_ml_doctor_tools(STORE):
        registry.register(tool)
    return MLDoctorAgent(registry)


def _retraining() -> BaseAgent:
    from retraining_agent.agent import RetrainingAgent
    from retraining_agent.tools import build_retraining_tools

    registry = ToolRegistry()
    for tool in build_retraining_tools(STORE):
        registry.register(tool)
    return RetrainingAgent(registry)


def _airflow_optimizer() -> BaseAgent:
    from airflow_optimizer.agent import AirflowOptimizerAgent
    from airflow_optimizer.tools import build_airflow_opt_tools

    registry = ToolRegistry()
    for tool in build_airflow_opt_tools(STORE):
        registry.register(tool)
    return AirflowOptimizerAgent(registry)


def _lineage() -> BaseAgent:
    from lineage_copilot.agent import LineageCopilotAgent
    from lineage_copilot.tools import build_lineage_tools

    registry = ToolRegistry()
    for tool in build_lineage_tools(STORE):
        registry.register(tool)
    return LineageCopilotAgent(registry)


def _migration() -> BaseAgent:
    from migration_agent.agent import MigrationAgent
    from migration_agent.tools import build_migration_tools

    registry = ToolRegistry()
    for tool in build_migration_tools(STORE):
        registry.register(tool)
    return MigrationAgent(registry)


def _engineering_os() -> BaseAgent:
    from engineering_os.orchestrator import EngineeringOrchestrator

    return EngineeringOrchestrator()


FACTORIES: dict[str, Any] = {
    "pipeline_sre": _pipeline_sre,
    "dbt_review": _dbt_review,
    "snowflake_optimizer": _snowflake_optimizer,
    "data_quality": _data_quality,
    "data_contract": _data_contract,
    "feature_engineering": _feature_engineering,
    "ml_doctor": _ml_doctor,
    "retraining": _retraining,
    "airflow_optimizer": _airflow_optimizer,
    "lineage_copilot": _lineage,
    "migration": _migration,
    "engineering_os": _engineering_os,
}


def create_agent(name: str) -> BaseAgent:
    if name not in FACTORIES:
        raise KeyError(f"Unknown agent: {name}. Available: {sorted(FACTORIES)}")
    return FACTORIES[name]()


def list_agents() -> list[dict[str, str]]:
    return [
        {"name": name, "factory": fn.__name__}
        for name, fn in FACTORIES.items()
    ]
