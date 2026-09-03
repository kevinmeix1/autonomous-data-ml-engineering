# dbt Review Agent

Autonomous dbt PR reviewer that inspects changed models, runs deterministic static SQL checks, pulls real dbt test results from the platform store, analyzes lineage/cost, and emits structured findings.

## Import paths

- `dbt_review.agent.DbtReviewAgent`
- `dbt_review.tools.build_dbt_review_tools(store)`

## Tools

| Tool | Risk |
|------|------|
| `inspect_pr_files` | READ_ONLY |
| `get_dbt_manifest` | READ_ONLY |
| `get_model_sql` | READ_ONLY |
| `run_static_checks` | READ_ONLY |
| `run_dbt_tests` | READ_ONLY |
| `get_lineage` | READ_ONLY |
| `get_query_characteristics` | READ_ONLY |
| `estimate_cost` | READ_ONLY |
