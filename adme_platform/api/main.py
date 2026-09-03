from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import adme_platform.bootstrap  # noqa: F401
from observability.audit import AuditRecord
from adme_platform.api.agent_factory import create_agent, list_agents
from adme_platform.api.store import STORE

app = FastAPI(
    title="Autonomous Data & ML Engineering OS",
    description="AI-powered autonomous data and ML engineering platform (synthetic insurance lab)",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class RunAgentRequest(BaseModel):
    agent: str
    objective: str
    context: dict[str, Any] = Field(default_factory=dict)


class ApprovalRequest(BaseModel):
    execution_id: str
    action_id: str
    decision: str  # approve | reject
    approver: str = "human"
    reason: str = ""


@app.get("/ready")
def ready() -> dict[str, str]:
    STORE.load_or_generate()
    return {"status": "ready"}


@app.middleware("http")
async def ensure_store(request, call_next):
    if STORE.platform is None and request.url.path not in {"/health", "/docs", "/openapi.json"}:
        STORE.load_or_generate()
    return await call_next(request)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "mode": "LOCAL_SIMULATION"}


@app.get("/agents")
def agents() -> list[dict[str, str]]:
    return list_agents()


@app.get("/overview")
def overview() -> dict[str, Any]:
    p = STORE.require()
    return {
        "tables": len(p.tables),
        "dags": len(p.dags),
        "dbt_models": len(p.dbt_models),
        "incidents_open": sum(1 for i in p.incidents if i.status == "open"),
        "failed_tests": sum(1 for t in p.dbt_tests if t.status == "fail"),
        "models": len(p.models),
        "features": len(p.features),
        "queries": len(p.queries),
        "observability": STORE.obs.summary(),
        "executions": len(STORE.executions),
    }


@app.get("/incidents")
def incidents() -> list[dict[str, Any]]:
    return [i.model_dump(mode="json") for i in STORE.require().incidents]


@app.get("/pipelines")
def pipelines() -> list[dict[str, Any]]:
    return [d.model_dump(mode="json") for d in STORE.require().dags]


@app.get("/dbt/models")
def dbt_models() -> list[dict[str, Any]]:
    return [m.model_dump(mode="json") for m in STORE.require().dbt_models]


@app.get("/dbt/tests")
def dbt_tests() -> list[dict[str, Any]]:
    return [t.model_dump(mode="json") for t in STORE.require().dbt_tests]


@app.get("/snowflake/queries")
def queries(limit: int = 50) -> list[dict[str, Any]]:
    qs = sorted(STORE.require().queries, key=lambda q: q.credits_used, reverse=True)
    return [q.model_dump(mode="json") for q in qs[:limit]]


@app.get("/snowflake/warehouses")
def warehouses() -> list[dict[str, Any]]:
    return [m.model_dump(mode="json") for m in STORE.require().warehouse_metrics[:100]]


@app.get("/ml/models")
def ml_models() -> list[dict[str, Any]]:
    return [m.model_dump(mode="json") for m in STORE.require().models]


@app.get("/features")
def features() -> list[dict[str, Any]]:
    return [f.model_dump(mode="json") for f in STORE.require().features]


@app.get("/contracts")
def contracts() -> list[dict[str, Any]]:
    return [c.model_dump(mode="json") for c in STORE.require().contracts]


@app.get("/lineage")
def lineage(node_id: str | None = None) -> dict[str, Any]:
    if node_id:
        return {
            "node_id": node_id,
            "upstream": STORE.lineage.upstream(node_id),
            "downstream": STORE.lineage.downstream(node_id),
            "impact": STORE.lineage.impact(node_id),
        }
    return STORE.lineage.to_cytoscape()


@app.get("/audit")
def audit(limit: int = 200) -> list[dict[str, Any]]:
    return [r.model_dump(mode="json") for r in STORE.audit.list(limit=limit)]


@app.get("/observability")
def observability() -> dict[str, Any]:
    return {"summary": STORE.obs.summary(), "events": [e.model_dump(mode="json") for e in STORE.obs.events[-200:]]}


@app.get("/executions")
def executions() -> list[dict[str, Any]]:
    return list(STORE.executions.values())


@app.get("/executions/{execution_id}")
def get_execution(execution_id: str) -> dict[str, Any]:
    if execution_id not in STORE.executions:
        raise HTTPException(404, "Execution not found")
    return STORE.executions[execution_id]


@app.post("/agents/run")
def run_agent(req: RunAgentRequest) -> dict[str, Any]:
    try:
        agent = create_agent(req.agent)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc

    execution = agent.run(req.objective, req.context)
    view = execution.public_view()
    STORE.save_execution(view)
    STORE.audit.append(
        AuditRecord(
            who=req.agent,
            what="agent.run",
            why=req.objective,
            agent=req.agent,
            result={"execution_id": execution.execution_id, "state": execution.state.value},
        )
    )
    # Keep agent instance for approval workflow
    STORE.approvals[execution.execution_id] = {"agent": agent, "view": view}
    return view


@app.post("/approvals")
def approvals(req: ApprovalRequest) -> dict[str, Any]:
    entry = STORE.approvals.get(req.execution_id)
    if not entry:
        raise HTTPException(404, "Execution not found for approval")
    agent = entry["agent"]
    if req.decision == "approve":
        # Explicit confirmation required for production-style changes
        result = agent.approve_action(req.action_id, approver=req.approver)
        STORE.audit.append(
            AuditRecord(
                who=req.approver,
                what="approve_action",
                why=req.reason or "human approval",
                agent=agent.name,
                approval={"action_id": req.action_id, "decision": "approved"},
                result=result,
            )
        )
    elif req.decision == "reject":
        agent.reject_action(req.action_id, approver=req.approver, reason=req.reason)
        STORE.audit.append(
            AuditRecord(
                who=req.approver,
                what="reject_action",
                why=req.reason or "human rejection",
                agent=agent.name,
                approval={"action_id": req.action_id, "decision": "rejected"},
            )
        )
        result = {"status": "rejected"}
    else:
        raise HTTPException(400, "decision must be approve|reject")

    view = agent.execution.public_view()
    STORE.save_execution(view)
    entry["view"] = view
    return view


@app.post("/data/regenerate")
def regenerate(seed: int = 42) -> dict[str, Any]:
    platform = STORE.load_or_generate(seed=seed)
    # force regenerate
    from data_generation.generator import generate_platform

    STORE.platform = generate_platform(seed=seed)
    STORE.platform.to_files(STORE.data_dir)
    STORE._build_lineage()
    return {"status": "ok", "incidents": len(platform.incidents)}
