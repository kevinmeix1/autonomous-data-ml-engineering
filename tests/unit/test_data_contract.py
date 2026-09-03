from data_contract_agent.agent import DataContractAgent
from data_contract_agent.tools import build_contract_tools

from tests.unit.conftest import build_agent


def test_data_contract_schema_change():
    agent, _ = build_agent(DataContractAgent, build_contract_tools)
    res = agent.call_tool("analyze_schema_change", {"table_id": "RAW.CLAIM.claims"})
    assert res["success"]
    assert "changes" in res["output"]


def test_data_contract_agent_run():
    agent, _ = build_agent(DataContractAgent, build_contract_tools)
    execution = agent.run(
        "Assess contract impact of claims schema change",
        {"table_id": "RAW.CLAIM.claims"},
    )
    assert execution.final_result["success"] is True
    assert execution.final_result.get("breaking") is True
    assert "risk" in execution.final_result
