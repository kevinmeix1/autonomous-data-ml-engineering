# Snowflake Optimization Guidance

- Prefer pruning predicates and clustering on high-filter columns
- Avoid repeated full scans of fct_claims in hourly jobs
- Right-size warehouses; XL for bursty transforms often wastes credits
- Materialize expensive reused subqueries
- Track bytes_scanned and credits_used as cost proxies
