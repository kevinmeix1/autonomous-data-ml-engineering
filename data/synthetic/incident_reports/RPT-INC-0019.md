# Incident Report RPT-INC-0019

**Root cause:** snowflake_query_timeout

**Summary:** Investigate incident INC-0019: score_claims_model failed due to upstream

**Remediation:** rerun_dbt_model:{'model_unique_id': 'model.analytics.fct_claims'}

**Evidence:**
- log_match:timeout|000630|57014