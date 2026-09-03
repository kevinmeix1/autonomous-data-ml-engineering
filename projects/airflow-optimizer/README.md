# Airflow Optimizer

Analyzes Airflow DAGs for critical path, bottlenecks, parallelizable tasks, dependency depth, and high-failure nodes.

## Tools

| Tool | Risk | Description |
|------|------|-------------|
| `get_dag_graph` | READ_ONLY | DAG task graph |
| `compute_critical_path` | READ_ONLY | Longest path analysis |
| `analyze_task_durations` | READ_ONLY | Duration statistics |
| `find_bottlenecks` | READ_ONLY | Bottleneck and failure nodes |
| `recommend_dag_changes` | READ_ONLY | parallelize/schedule/retries/split |
| `apply_dag_change` | APPROVAL_REQUIRED | Apply optimization |

## Usage

```python
from adme_platform.api.agent_factory import create_agent

agent = create_agent("airflow_optimizer")
execution = agent.run(
    "Optimize insurance daily pipeline",
    context={"dag_id": "insurance_daily_pipeline"},
)
```
