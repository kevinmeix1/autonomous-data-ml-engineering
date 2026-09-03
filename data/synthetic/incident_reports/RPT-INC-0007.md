# Incident Report RPT-INC-0007

**Root cause:** warehouse_overload

**Summary:** Investigate incident INC-0007: TRANSFORM_WH overload delaying pipeline

**Remediation:** restart_task:{'dag_id': 'insurance_daily_pipeline', 'task_id': 'dbt_run_core'}

**Evidence:**
- log_match:queued_overload|overload
- log_match:queued_overload|overload