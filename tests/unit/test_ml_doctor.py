from tool_sdk.registry import ToolRegistry

from ml_doctor.agent import MLDoctorAgent
from ml_doctor.tools import build_ml_doctor_tools


def test_build_ml_doctor_tools_count(store):
    tools = build_ml_doctor_tools(store)
    names = {t.name for t in tools}
    assert len(tools) == 7
    assert "get_model_metrics" in names
    assert "detect_drift" in names
    assert "diagnose_incident" in names


def test_get_model_metrics(store):
    registry = ToolRegistry()
    for tool in build_ml_doctor_tools(store):
        registry.register(tool)
    result = registry.call(
        "get_model_metrics",
        {"model_id": "ml.claims_severity_v3"},
        context=_ctx(),
    )
    assert result.success
    assert result.output.model_id == "ml.claims_severity_v3"
    assert "auc" in result.output.metrics


def test_detect_drift(store):
    registry = ToolRegistry()
    for tool in build_ml_doctor_tools(store):
        registry.register(tool)
    result = registry.call(
        "detect_drift",
        {"model_id": "ml.claims_severity_v3", "feature": "avg_incurred_12m", "method": "both"},
        context=_ctx(),
    )
    assert result.success
    assert result.output.results[0].psi is not None


def test_ml_doctor_agent_run(store):
    registry = ToolRegistry()
    for tool in build_ml_doctor_tools(store):
        registry.register(tool)
    agent = MLDoctorAgent(registry)
    execution = agent.run(
        "Investigate model degradation",
        context={"model_id": "ml.claims_severity_v3"},
    )
    assert execution.final_result["success"] is True
    assert execution.final_result["problem_domain"] in {
        "DATA", "MODEL", "INFRASTRUCTURE", "BUSINESS-DISTRIBUTION", "UNKNOWN"
    }


def _ctx():
    from tool_sdk.base import ToolContext
    return ToolContext(execution_id="test", agent_name="ml_doctor")
