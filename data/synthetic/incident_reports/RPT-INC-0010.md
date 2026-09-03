# Incident Report RPT-INC-0010

**Root cause:** upstream_failure

**Summary:** Investigate incident INC-0010: Upstream extract_claims task failed

**Remediation:** restart_task:{'dag_id': 'insurance_daily_pipeline', 'task_id': 'extract_claims'}

**Evidence:**
- log_match:Connection refused|SourceExtractError|SFTP
- log_match:Connection refused|SourceExtractError|SFTP