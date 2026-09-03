# Ablation Study Design

## Questions

1. Do structured diagnostic tools outperform LLM-only RCA?
2. Does lineage improve root-cause accuracy?
3. Does tool-use reduce hallucinated statistics?
4. What is the accuracy vs token-cost frontier under model routing?

## Protocol

For each scenario in `benchmarks/scenarios.json`, run:

| Config | Description |
|---|---|
| A | LLM-only narrative diagnosis (no tools) |
| B | LLM + RAG runbooks |
| C | Deterministic tools + rules (no LLM) |
| D | LLM + tools + structured state |
| E | Multi-agent Engineering OS |

Report accuracy, cost, latency, tool calls, failure rate.

Baseline implementation for config C/D is `pipeline_sre` (rules + tools).
