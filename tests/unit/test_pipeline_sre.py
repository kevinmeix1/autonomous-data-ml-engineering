from adme_platform.api.store import STORE
from pipeline_sre.agent import PipelineSREAgent
from pipeline_sre.rca import merge_candidates, score_from_logs
from pipeline_sre.tools import build_pipeline_tools
from tool_sdk.registry import ToolRegistry


def test_rca_from_logs():
    cands = score_from_logs(["[ERROR] Connection refused to claims source SFTP"])
    best = merge_candidates(cands)
    assert best is not None
    assert best.root_cause == "upstream_failure"


def test_pipeline_sre_agent_run():
    STORE.load_or_generate(seed=42)
    reg = ToolRegistry()
    for t in build_pipeline_tools(STORE):
        reg.register(t)
    agent = PipelineSREAgent(reg)
    execution = agent.run(
        "Investigate insurance_daily_pipeline failure",
        {"dag_id": "insurance_daily_pipeline", "incident_id": "INC-0000"},
    )
    assert execution.final_result is not None
    assert execution.tool_calls
    assert execution.final_result.get("root_cause")
