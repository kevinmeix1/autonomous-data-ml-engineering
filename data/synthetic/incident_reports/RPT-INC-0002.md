# Incident Report RPT-INC-0002

**Root cause:** missing_partition

**Summary:** Investigate incident INC-0002: Missing partition for claims load date

**Remediation:** restart_task:{'dag_id': 'insurance_daily_pipeline', 'task_id': 'load_raw_claims'}

**Evidence:**
- log_match:Partition not found|s3://.*dt=
- log_match:Partition not found|s3://.*dt=