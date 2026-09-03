# Strict Critic Review — ADME 12 Labs

Source-level staff review ([Critic review 12 labs](dbe89990-1627-4923-aa9a-985a22d706d8)) plus verification in this session.

## Positioning (honest)

**Deterministic multi-agent diagnostic framework** with typed tools, approval-gated remediation, and a control-plane UI — not “fully autonomous LLM agents.” OpenAI keys in `.env.example` are optional future planner hooks; runtime agents today are imperative tool workflows.

| Lens | Score |
|---|---|
| Demo / simulation portfolio | **~6–8/10** (Pipeline SRE strongest) |
| Deployable production autonomy | **~3/10** (no real cloud writes; fabricated metrics in some ML/cost paths) |

## Verified this session

| Check | Result |
|---|---|
| `pytest` | 46 passed |
| 12/12 agent smoke | ok |
| Isolated Pipeline SRE benchmark | **90%** diagnosis accuracy, 0 safety violations |
| Failure injection duplicates | recovers `duplicate_records` |

## P0 follow-ups applied after critic

1. **Data contract approval bug fixed** — high-risk path now proposes `publish_contract_version` (APPROVAL_REQUIRED write), not READ_ONLY `recommend_action`.
2. **Global LOCAL_SIMULATION banner** in UI shell + reframed README.
3. **Evaluation CLI isolated mode** (`evaluation.cli run --isolated`, default on) for Pipeline SRE.

## Remaining gaps (not yet fixed)

- Eval suites for the other 11 agents
- Fabricated paths: Snowflake `measure_impact` ~92% fudge, DQ/ML synthetic column series, retraining +0.03 AUC
- RAG / KnowledgeBase unused by agents
- Engineering OS is a sequential router, not a full blackboard OS

## PDF

Full lab deep-dives + diagrams: [`docs/portfolio/ADME_12_Labs_Portfolio.pdf`](portfolio/ADME_12_Labs_Portfolio.pdf)
