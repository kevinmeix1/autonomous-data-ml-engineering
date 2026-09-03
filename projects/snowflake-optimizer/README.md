# Snowflake Optimizer Agent

Discovers expensive queries, ranks warehouses and dbt models, estimates savings, proposes optimizations (approval-gated apply), and measures predicted vs actual impact.

## Import paths

- `snowflake_optimizer.agent.SnowflakeOptimizerAgent`
- `snowflake_optimizer.tools.build_cost_tools(store)`

## Loop

discover → rank → investigate → estimate → recommend → approval → apply → measure
