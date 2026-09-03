# Evaluation Methodology

1. Generate synthetic platform + scenarios (`make generate-data`)
2. Each scenario includes `ground_truth_root_cause` and `expected_tools`
3. Run agents via `make evaluate`
4. Aggregate: success rate, diagnosis accuracy, remediation success, tool calls, latency, cost, safety violations

## Ablations

Compare configurations in `experiments/`:

- LLM only
- LLM + RAG
- LLM + tools
- LLM + tools + structured state
- Multi-agent orchestrator
