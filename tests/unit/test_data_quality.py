from data_quality_agent.agent import DataQualityAgent
from data_quality_agent.tools import build_dq_tools

from tests.unit.conftest import build_agent


def test_data_quality_psi_tool():
    agent, _ = build_agent(DataQualityAgent, build_dq_tools)
    res = agent.call_tool(
        "compute_psi",
        {"table_id": "RAW.CLAIM.claims", "column": "incurred_amount"},
    )
    assert res["success"]
    assert "psi" in res["output"]


def test_data_quality_agent_run():
    agent, _ = build_agent(DataQualityAgent, build_dq_tools)
    execution = agent.run(
        "Investigate null spike on claims",
        {
            "table_id": "RAW.CLAIM.claims",
            "column": "incurred_amount",
            "hypothesis": "Distribution drift on incurred_amount",
        },
    )
    assert execution.final_result["success"] is True
    assert "statistical_tests" in execution.final_result
