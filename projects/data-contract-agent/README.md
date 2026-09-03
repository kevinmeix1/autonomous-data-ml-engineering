# Data Contract Agent

Guards data contracts when schemas change: analyze diffs, trace lineage impact, assess risk to dbt models/features/SageMaker models, and recommend governance actions.

## Import paths

- `data_contract_agent.agent.DataContractAgent`
- `data_contract_agent.tools.build_contract_tools(store)`

## Workflow

analyze → lineage → impact → risk → recommendation
