from engineering_os.orchestrator import EngineeringOrchestrator, route_agents


def test_route_agents_model_degradation():
    agents = route_agents("Claims model performing worse")
    assert agents[0] == "ml_doctor"
    assert "retraining" in agents
    assert "lineage_copilot" in agents


def test_route_agents_custom():
    agents = route_agents("anything", context={"agents": ["ml_doctor", "migration"]})
    assert agents == ["ml_doctor", "migration"]


def test_engineering_orchestrator_run(store):
    from adme_platform.api.store import STORE
    STORE.load_or_generate(seed=42)

    orchestrator = EngineeringOrchestrator()
    execution = orchestrator.run(
        "Claims model performing worse",
        context={"model_id": "ml.claims_severity_v3"},
    )
    assert execution.agent == "engineering_os"
    assert execution.final_result["success"] is True
    assert "ml_doctor" in execution.final_result["agent_results"]
    sub = orchestrator.get_sub_executions()
    assert len(sub) >= 1
