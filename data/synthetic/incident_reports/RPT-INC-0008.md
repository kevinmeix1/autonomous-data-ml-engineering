# Incident Report RPT-INC-0008

**Root cause:** invalid_sql

**Summary:** Investigate incident INC-0008: Invalid SQL in feat_policy_risk model

**Remediation:** create_incident_report:{'incident_id': 'invalid_sql', 'root_cause': 'invalid_sql', 'summary': 'Fix SQL identifier typo', 'remediation': 'Correct POLICY_RISK_SCOR typo and rerun'}

**Evidence:**
- log_match:invalid identifier|SQL compilation error
- log_match:invalid identifier|SQL compilation error