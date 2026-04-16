.PHONY: venv install dev test lint typecheck security run docker fmt clean smoke-aurora smoke-moonboard smoke-crux

VENV ?= .venv
PY := $(VENV)/bin/python
PIP := $(VENV)/bin/pip
UVICORN := $(VENV)/bin/uvicorn
PYTEST := $(VENV)/bin/pytest
RUFF := $(VENV)/bin/ruff
MYPY := $(VENV)/bin/mypy
PIP_AUDIT := $(VENV)/bin/pip-audit
BANDIT := $(VENV)/bin/bandit

$(VENV)/bin/python:
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -e ".[dev]"

venv: $(VENV)/bin/python

install: venv

dev: venv
	$(UVICORN) kt.main:app --reload --host 0.0.0.0 --port 8000

run: venv
	$(UVICORN) kt.main:app --host 0.0.0.0 --port 8000

test: venv
	$(PYTEST) -q

lint: venv
	$(RUFF) check src tests

fmt: venv
	$(RUFF) format src tests

typecheck: venv
	$(MYPY) src

security: venv
	$(PIP_AUDIT)
	$(BANDIT) -q -r src/kt -x tests

docker:
	docker compose up --build

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache build dist *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} +

smoke-aurora: venv
	$(PY) -m scripts.smoke_aurora

smoke-moonboard: venv
	$(PY) -m scripts.smoke_moonboard

smoke-crux: venv
	$(PY) -m scripts.smoke_crux
