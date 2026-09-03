# Lineage Copilot

Insurance domain lineage explorer — policies, claims, customers, exposures, premiums, features, and ML models. All answers cite evidence from `STORE.lineage` graph edges.

## Tools

| Tool | Risk | Description |
|------|------|-------------|
| `find_upstream` | READ_ONLY | Upstream nodes with edge evidence |
| `find_downstream` | READ_ONLY | Downstream nodes with edge evidence |
| `find_feature_origin` | READ_ONLY | Feature → table lineage |
| `find_models_using_table` | READ_ONLY | Table → ML model dependencies |
| `find_tables_used_by_model` | READ_ONLY | Model → table/feature inputs |
| `explain_transformation` | READ_ONLY | Transformation between nodes |
| `identify_impact` | READ_ONLY | Downstream blast radius |

## Usage

```python
from adme_platform.api.agent_factory import create_agent

agent = create_agent("lineage_copilot")
execution = agent.run(
    "What models use claims data?",
    context={"node_id": "RAW.CLAIM.claims", "model_id": "ml.claims_severity_v3"},
)
```
