from domain.enums import ActionRisk
from tool_sdk.registry import ToolRegistry

from retraining_agent.agent import RetrainingAgent
from retraining_agent.tools import build_retraining_tools


def test_build_retraining_tools(store):
    tools = build_retraining_tools(store)
    assert len(tools) == 9
    deploy = next(t for t in tools if t.name == "deploy_model")
    assert deploy.risk == ActionRisk.APPROVAL_REQUIRED


def test_champion_challenger_flow(store):
    registry = ToolRegistry()
    for tool in build_retraining_tools(store):
        registry.register(tool)
    ctx = _ctx()

    train = registry.call("train_candidate", {"model_id": "ml.claims_severity_v3"}, ctx)
    assert train.success
    assert "LOCAL_SIMULATION" in train.output.message or train.output.mode == "LOCAL_SIMULATION"

    cid = train.output.candidate_id
    compare = registry.call(
        "compare_champion_challenger",
        {
            "champion_model_id": "ml.claims_severity_v3",
            "candidate_id": cid,
            "promotion_policy": "auc_improvement",
        },
        ctx,
    )
    assert compare.success
    assert compare.output.promote is True


def test_deploy_requires_approval(store):
    registry = ToolRegistry()
    for tool in build_retraining_tools(store):
        registry.register(tool)
    ctx = _ctx()
    train = registry.call("train_candidate", {"model_id": "ml.claims_severity_v3"}, ctx)
    result = registry.call(
        "deploy_model",
        {
            "candidate_id": train.output.candidate_id,
            "champion_model_id": "ml.claims_severity_v3",
        },
        ctx,
    )
    assert not result.success
    assert result.approval_required


def test_retraining_agent_run(store):
    registry = ToolRegistry()
    for tool in build_retraining_tools(store):
        registry.register(tool)
    agent = RetrainingAgent(registry)
    execution = agent.run(
        "Retrain degraded model",
        context={"model_id": "ml.claims_severity_v3", "force_retrain": True},
    )
    assert execution.final_result["retrained"] is True
    assert "LOCAL_SIMULATION" in execution.final_result.get("mode", "")


def _ctx():
    from tool_sdk.base import ToolContext
    return ToolContext(execution_id="test", agent_name="retraining")
