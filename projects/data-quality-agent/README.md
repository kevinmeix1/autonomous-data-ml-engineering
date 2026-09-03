# Data Quality Agent

Investigates data quality across completeness, uniqueness, validity, consistency, freshness, referential integrity, distribution stability, and volume using deterministic statistical tools (PSI, KS, IQR outliers).

## Import paths

- `data_quality_agent.agent.DataQualityAgent`
- `data_quality_agent.tools.build_dq_tools(store)`

## Tools

`profile_table`, `get_historical_distribution`, `get_lineage`, `get_upstream_changes`, `compute_psi`, `compute_ks_test`, `detect_outliers`, `hypothesis_test`
