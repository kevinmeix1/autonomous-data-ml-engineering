# Retraining Agent

Champion/challenger retraining lifecycle with safety gates and approval-gated deploy/rollback. All write operations are clearly labeled `LOCAL_SIMULATION` vs `REAL_AWS`.

## Tools

| Tool | Risk | Description |
|------|------|-------------|
| `assess_degradation` | READ_ONLY | Check if retraining is needed |
| `build_training_dataset` | SAFE_AUTOMATION | Build training dataset |
| `train_candidate` | SAFE_AUTOMATION | Train challenger |
| `evaluate_candidate` | READ_ONLY | Holdout evaluation |
| `compare_champion_challenger` | READ_ONLY | Promotion policy comparison |
| `check_safety_gates` | READ_ONLY | Pre-deploy safety gates |
| `deploy_model` | APPROVAL_REQUIRED | Deploy challenger |
| `rollback_model` | APPROVAL_REQUIRED | Rollback to previous version |
| `monitor_post_deploy` | READ_ONLY | Post-deploy health check |

## Usage

```python
from adme_platform.api.agent_factory import create_agent

agent = create_agent("retraining")
execution = agent.run(
    "Retrain claims severity model",
    context={"model_id": "ml.claims_severity_v3", "promotion_policy": "auc_improvement"},
)
```
