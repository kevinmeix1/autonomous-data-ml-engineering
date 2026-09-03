# Incident Report RPT-INC-0011

**Root cause:** schema_change

**Summary:** Investigate incident INC-0011: Schema change broke stg_claims

**Remediation:** create_incident_report:{'incident_id': 'schema', 'root_cause': 'schema_change', 'summary': 'Update accepted values / contract', 'remediation': 'Update dbt accepted_values and data contract'}

**Evidence:**
- log_match:unexpected value|accepted_values|schema|REOPENED
- failed_test:accepted_values_stg_claims_claim_status
- log_match:unexpected value|accepted_values|schema|REOPENED