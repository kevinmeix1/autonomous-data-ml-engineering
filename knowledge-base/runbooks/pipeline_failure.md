# Pipeline Failure Runbook

## Observe
1. Check Airflow DAG status and failed tasks.
2. Pull task logs for the earliest failed upstream task.
3. Inspect dbt test failures and Snowflake query history.

## Common causes
- Upstream extract/SFTP failure
- Schema drift on claim_status enums
- Missing S3 partitions
- Null spikes / duplicate keys after replay
- Warehouse overload / query timeout

## Remediation
- Restart extract only after source availability confirmed
- Update accepted_values + data contracts for schema changes
- Do not blindly rerun incremental models with duplicates — dedupe first
