# ML Doctor

Autonomous ML model health monitor for insurance ML platforms. Detects drift, calibration issues, latency anomalies, and infrastructure failures using statistical tests (PSI, KS).

## Tools

| Tool | Risk | Description |
|------|------|-------------|
| `get_model_metrics` | READ_ONLY | Training/validation metrics |
| `get_feature_distributions` | READ_ONLY | Feature distribution stats |
| `detect_drift` | READ_ONLY | PSI/KS drift detection |
| `get_inference_stats` | READ_ONLY | Endpoint latency and errors |
| `get_feature_pipeline_status` | READ_ONLY | Feature pipeline health |
| `diagnose_incident` | READ_ONLY | Classify DATA/MODEL/INFRA/BUSINESS issues |
| `recommend_action` | READ_ONLY | Remediation recommendations |

## Usage

```python
from adme_platform.api.store import STORE
from tool_sdk.registry import ToolRegistry
from ml_doctor.tools import build_ml_doctor_tools
from ml_doctor.agent import MLDoctorAgent

STORE.load_or_generate()
registry = ToolRegistry()
for tool in build_ml_doctor_tools(STORE):
    registry.register(tool)

agent = MLDoctorAgent(registry)
execution = agent.run(
    "Investigate claims model degradation",
    context={"model_id": "ml.claims_severity_v3"},
)
```

Or via factory:

```python
from adme_platform.api.agent_factory import create_agent

agent = create_agent("ml_doctor")
execution = agent.run("Investigate claims model degradation")
```
