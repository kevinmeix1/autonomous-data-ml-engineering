# Incident Report RPT-INJ

**Root cause:** duplicate_records

**Summary:** Investigate duplicates

**Remediation:** rerun_dbt_model:{'model_unique_id': 'model.analytics.fct_claims'}

**Evidence:**
- log_match:unique_.*claim|duplicate
- failed_test:unique_fct_claims_claim_id
- failed_test:unique_fct_claims_claim_id
- log_match:unique_.*claim|duplicate