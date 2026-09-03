from agent_sdk.state import AgentExecution, Finding
from domain.enums import EvidenceKind, IncidentSeverity
from evaluation.metrics import diagnostic_accuracy, evaluate_execution


def test_diagnostic_accuracy():
    assert diagnostic_accuracy("schema_change", "schema_change") == 1.0
    assert diagnostic_accuracy("null spike", "null_spike") >= 0.5


def test_evaluate_execution():
    ex = AgentExecution(agent="pipeline_sre", objective="x")
    ex.findings.append(
        Finding(
            title="duplicate_records",
            severity=IncidentSeverity.HIGH,
            kind=EvidenceKind.OBSERVED_FACT,
            explanation="dupes",
            evidence_ids=["e1"],
        )
    )
    ex.final_result = {"root_cause": "duplicate_records", "success": True, "remediation_success": True}
    report = evaluate_execution(
        ex,
        scenario_id="s1",
        ground_truth_root_cause="duplicate_records",
        expected_tools=["get_dbt_tests"],
    )
    assert report.diagnostic_accuracy == 1.0
    assert report.task_success
