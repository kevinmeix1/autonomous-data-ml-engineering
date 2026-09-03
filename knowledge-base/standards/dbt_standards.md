# dbt Standards

- Staging models are views; core facts may be incremental with unique_key
- Every fact table requires uniqueness + not_null tests on keys
- Document all marts and features
- Avoid select * in production models
- Incremental filters must use reliable watermark columns (prefer report_date, not updated_at alone)
- Never join without cardinality analysis (fanout risk)
