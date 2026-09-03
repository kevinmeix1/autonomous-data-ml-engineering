# Incident Report RPT-INC-0004

**Root cause:** duplicate_records

**Summary:** Investigate incident INC-0004: Duplicate claim_id in fct_claims

**Remediation:** rerun_dbt_model:{'model_unique_id': 'model.analytics.fct_claims'}

**Evidence:**
- log_match:unique_.*claim|duplicate
- failed_test:unique_fct_claims_claim_id
- log_match:unique_.*claim|duplicate