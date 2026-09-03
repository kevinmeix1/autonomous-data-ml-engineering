# Autonomous Data & ML Engineering Agent Lab

Production-style portfolio of **12 deterministic diagnostic agents** for a synthetic commercial-insurance data/ML platform (Airflow, dbt, Snowflake, SageMaker — **LOCAL_SIMULATION**).

> Agents use real typed tools, inspect system state, form hypotheses, require approval for high-risk actions, and (for Pipeline SRE) are evaluated against ground-truth failure scenarios. Workflows are structured Python diagnostic loops — not unconstrained chatbots. An optional LLM planner can be layered later behind the same tool contracts.

## Quick start

```bash
make setup
make generate-data
make run          # API :8000
make run-ui       # UI  :3000
```

```bash
make test
make evaluate
```

## Monorepo layout

```
projects/          # 12 agent systems
shared/            # agent-sdk, tool-sdk, evaluation, domain, data-generation, graph, retrieval
adme_platform/          # FastAPI + Next.js control center
benchmarks/        # ground-truth scenarios
knowledge-base/    # runbooks & standards (RAG)
experiments/       # ablation / research
infrastructure/    # Docker Compose
tests/
```

## Agents

| # | Agent | Folder |
|---|---|---|
| 1 | Pipeline SRE | `projects/pipeline-sre` |
| 2 | dbt Review | `projects/dbt-review` |
| 3 | Snowflake Cost Optimizer | `projects/snowflake-optimizer` |
| 4 | Data Quality Investigator | `projects/data-quality-agent` |
| 5 | Data Contract Guardian | `projects/data-contract-agent` |
| 6 | Feature Engineering | `projects/feature-engineering-agent` |
| 7 | ML Pipeline Doctor | `projects/ml-doctor` |
| 8 | Model Retraining | `projects/retraining-agent` |
| 9 | Airflow DAG Optimizer | `projects/airflow-optimizer` |
| 10 | Insurance Lineage Copilot | `projects/lineage-copilot` |
| 11 | Data Migration | `projects/migration-agent` |
| 12 | Engineering OS Orchestrator | `projects/engineering-os` |

## Safety model

| Class | Examples |
|---|---|
| READ_ONLY | metadata, logs, lineage, profiles |
| SAFE_AUTOMATION | validation, reports, tests |
| APPROVAL_REQUIRED | restart tasks, deploy models, alter pipelines |
| PROHIBITED | arbitrary shell, unrestricted SQL, destructive DDL |

## Evaluation

Synthetic incidents include **ground-truth root causes**. Metrics:

- diagnostic accuracy
- false diagnosis rate
- tool efficiency
- remediation success
- latency / cost
- safety violations
- grounding score

## Modes

AWS SageMaker and Snowflake integrations default to **LOCAL_SIMULATION**. The UI and APIs never claim a simulated deploy was a real AWS execution.

## Docs & portfolio PDF

- Architecture: [`docs/architecture.md`](docs/architecture.md)
- Critic review: [`docs/CRITIC_REVIEW.md`](docs/CRITIC_REVIEW.md)
- **Full 12-lab PDF** (diagrams, deep dives, scores): [`docs/portfolio/ADME_12_Labs_Portfolio.pdf`](docs/portfolio/ADME_12_Labs_Portfolio.pdf)

```bash
make benchmark   # isolated RCA eval
make pdf         # regenerate portfolio PDF
```

## UI

Production-style mission control in `adme_platform/web` — agent evidence lanes, approvals inbox, DAG strip, lineage canvas, cost charts.
