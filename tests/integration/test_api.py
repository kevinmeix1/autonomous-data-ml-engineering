from fastapi.testclient import TestClient

from adme_platform.api.main import app
from adme_platform.api.store import STORE


client = TestClient(app)


def test_health_and_overview():
    STORE.load_or_generate(seed=42)
    assert client.get("/health").json()["status"] == "ok"
    overview = client.get("/overview").json()
    assert overview["tables"] > 0


def test_run_pipeline_sre_and_approval_flow():
    STORE.load_or_generate(seed=42)
    res = client.post(
        "/agents/run",
        json={
            "agent": "pipeline_sre",
            "objective": "Investigate insurance_daily_pipeline",
            "context": {"dag_id": "insurance_daily_pipeline", "incident_id": "INC-0000"},
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["execution_id"]
    assert body["tool_calls"]
    # If approval pending, exercise reject path safely
    pending = [a for a in body.get("actions", []) if a.get("status") == "proposed" and a.get("approval_required")]
    if pending:
        action_id = pending[0]["action_id"]
        rej = client.post(
            "/approvals",
            json={
                "execution_id": body["execution_id"],
                "action_id": action_id,
                "decision": "reject",
                "reason": "test",
            },
        )
        assert rej.status_code == 200
