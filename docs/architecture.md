# Architecture

```mermaid
flowchart TB
  UI[Next.js Control Center] --> API[FastAPI Platform API]
  API --> Orch[Engineering OS Orchestrator]
  Orch --> A1[Pipeline SRE]
  Orch --> A2[DQ Agent]
  Orch --> A3[dbt Review]
  Orch --> A4[Cost Optimizer]
  Orch --> A5[Contract Guardian]
  Orch --> A6[Feature Engineering]
  Orch --> A7[ML Doctor]
  Orch --> A8[Retraining]
  Orch --> A9[Airflow Optimizer]
  Orch --> A10[Lineage Copilot]
  Orch --> A11[Migration]
  A1 --> Tools[Tool SDK Allowlist]
  A2 --> Tools
  Tools --> Store[Synthetic Platform Store]
  Store --> AF[Airflow metadata]
  Store --> DBT[dbt runs/tests]
  Store --> SF[Snowflake query history]
  Store --> LG[Lineage Graph]
  Agents --> Eval[Evaluation SDK]
  Agents --> Obs[Observability + Audit]
  Agents --> KB[Knowledge Base RAG]
```

## Shared contracts

Every agent execution records:

`execution_id, agent, objective, state, tool_calls, hypotheses, findings, actions, approvals, final_result`

Public views expose investigation steps and evidence — not private chain-of-thought.

## Evidence classes (UI)

- Observed fact
- Model inference
- Agent hypothesis
- Recommended action
