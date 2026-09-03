# Project 1 — Autonomous Data Pipeline SRE Agent

Investigates Airflow / dbt / Snowflake / AWS-style pipeline failures with a deterministic RCA engine plus typed tools.

## Loop

Observe → Detect → Investigate → Hypothesize → Test → Root cause → Propose remediation → Approve → Execute → Verify → Document

## Run

```bash
# from repo root
python -c "from adme_platform.api.agent_factory import create_agent; print(create_agent('pipeline_sre').run('Investigate failure', {'dag_id':'insurance_daily_pipeline'}).final_result)"
```

Or use the UI **Agents** page / `POST /agents/run`.
