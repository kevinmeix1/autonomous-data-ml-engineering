# Setup

## Prerequisites

- Python 3.11+
- Node.js 20+
- Optional: Docker

## Local

```bash
cd autonomous-data-ml-engineering
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
make generate-data
make run      # API http://localhost:8000
make run-ui   # UI  http://localhost:3000
```

## Verify

```bash
make test
curl http://localhost:8000/health
curl http://localhost:8000/agents
```

## Docker

```bash
make docker-up
```
