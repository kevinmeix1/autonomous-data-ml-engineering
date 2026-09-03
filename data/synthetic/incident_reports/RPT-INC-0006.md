# Incident Report RPT-INC-0006

**Root cause:** snowflake_query_timeout

**Summary:** Investigate incident INC-0006: dbt_run_core Snowflake timeout

**Remediation:** rerun_dbt_model:{'model_unique_id': 'model.analytics.fct_claims'}

**Evidence:**
- log_match:timeout|000630|57014
- log_match:timeout|000630|57014