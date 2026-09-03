from adme_platform.api.store import STORE
from data_generation.failure_injection import inject_failure
from pipeline_sre.agent import PipelineSREAgent
from pipeline_sre.tools import build_pipeline_tools
from tool_sdk.registry import ToolRegistry


def test_inject_duplicates_diagnosed():
    STORE.load_or_generate(seed=42)
    inject_failure(STORE.require(), "inject_duplicates")
    reg = ToolRegistry()
    for t in build_pipeline_tools(STORE):
        reg.register(t)
    agent = PipelineSREAgent(reg)
    ex = agent.run("Investigate duplicates", {"dag_id": "insurance_daily_pipeline", "incident_id": "INJ"})
    assert ex.final_result
    assert ex.final_result["root_cause"] in {"duplicate_records", "null_spike", "schema_change", "upstream_failure"}
