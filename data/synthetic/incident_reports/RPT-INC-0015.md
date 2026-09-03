# Incident Report RPT-INC-0015

**Root cause:** data_freshness_failure

**Summary:** Investigate incident INC-0015: Claims table freshness SLA breached

**Remediation:** restart_task:{'dag_id': 'insurance_daily_pipeline', 'task_id': 'extract_claims'}

**Evidence:**
- log_match:freshness|SLA
- log_match:freshness|SLA