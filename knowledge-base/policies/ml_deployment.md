# ML Deployment Policy

- Champion/challenger required for production promotion
- Do not promote on a single metric improvement
- Safety gates: AUC drop < 2%, ECE within bound, latency p95 within SLO, no fairness regression
- Deployments require explicit human approval
- Local simulation must be labeled LOCAL_SIMULATION and never reported as REAL_AWS
