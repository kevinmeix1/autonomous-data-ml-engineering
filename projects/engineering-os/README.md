# Engineering OS

Multi-agent orchestrator that routes problems to specialized agents and aggregates evidence into a combined execution view.

## Routing Example

"Claims model performing worse" → `ml_doctor` → `data_quality` → `lineage_copilot` → `feature_engineering` → `retraining`

Agents not yet installed are skipped gracefully.

## Usage

```python
from adme_platform.api.agent_factory import create_agent

orchestrator = create_agent("engineering_os")
execution = orchestrator.run(
    "Claims model performing worse — investigate and retrain if needed",
    context={"model_id": "ml.claims_severity_v3"},
)

# Access sub-agent executions
from engineering_os.orchestrator import EngineeringOrchestrator
if isinstance(orchestrator, EngineeringOrchestrator):
    sub_execs = orchestrator.get_sub_executions()
```

## Custom routing

```python
execution = orchestrator.run(
    "Custom workflow",
    context={"agents": ["ml_doctor", "retraining"]},
)
```
