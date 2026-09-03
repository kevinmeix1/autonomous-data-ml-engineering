# Migration Agent

Legacy → Snowflake migration assistant. Never declares success without validation (row counts, null rates, aggregates, distributions).

## Tools

| Tool | Risk | Description |
|------|------|-------------|
| `inspect_legacy_schema` | READ_ONLY | Legacy schema inspection |
| `profile_table` | READ_ONLY | Table profiling |
| `map_columns` | READ_ONLY | Column mapping |
| `detect_type_incompatibilities` | READ_ONLY | Type mismatch detection |
| `generate_dbt_models` | SAFE_AUTOMATION | dbt model generation |
| `generate_tests` | SAFE_AUTOMATION | dbt test generation |
| `generate_reconciliation_sql` | READ_ONLY | Reconciliation SQL |
| `run_reconciliation` | SAFE_AUTOMATION | Run reconciliation checks |
| `validate_migration` | READ_ONLY | Gate success on validation |

## Usage

```python
from adme_platform.api.agent_factory import create_agent

agent = create_agent("migration")
execution = agent.run(
    "Migrate legacy claims to Snowflake",
    context={
        "legacy_table": "legacy.claims",
        "target_table": "RAW.CLAIM.claims",
    },
)
```
