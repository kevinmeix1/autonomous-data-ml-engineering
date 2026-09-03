.PHONY: setup test lint run evaluate generate-data demo docker-up docker-down clean

PYTHON ?= python3
VENV ?= .venv
PIP := $(VENV)/bin/pip
PY := $(VENV)/bin/python
# Prefer repo venv; fall back to parent lab venv if present
ifeq ($(wildcard $(VENV)/bin/python),)
  ifneq ($(wildcard ../.venv/bin/python),)
    PY := ../.venv/bin/python
    PIP := ../.venv/bin/pip
  endif
endif

setup:
	$(PYTHON) -m venv $(VENV) || true
	$(PIP) install -U pip
	$(PIP) install -e ".[dev]"
	cd adme_platform/web && npm install

generate-data:
	$(PY) -m data_generation.cli --seed 42 --output data/synthetic

test:
	$(PY) -m pytest -q --tb=short

lint:
	$(VENV)/bin/ruff check shared projects adme_platform tests || true

run:
	$(PY) -m uvicorn adme_platform.api.main:app --reload --host 0.0.0.0 --port 8000

run-ui:
	cd adme_platform/web && npm run dev

evaluate:
	$(PY) -m evaluation.cli run --suite benchmarks/scenarios.json --output data/eval_results.json

benchmark:
	$(PY) scripts/run_benchmark.py

pdf:
	MPLCONFIGDIR=.mplconfig $(PY) scripts/generate_portfolio_pdf.py
	@echo "Wrote docs/portfolio/ADME_12_Labs_Portfolio.pdf"

demo: generate-data
	$(PY) -c "from adme_platform.api.cli import seed; seed(42)"
	@echo "Demo data ready. Run: make run"

docker-up:
	docker compose -f infrastructure/docker-compose.yml up -d --build

docker-down:
	docker compose -f infrastructure/docker-compose.yml down

clean:
	rm -rf .pytest_cache **/__pycache__ .mypy_cache .ruff_cache data/synthetic/*.json data/eval_results.json
