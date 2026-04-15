.PHONY: dev test lint typecheck run docker fmt clean

PY ?= python3

dev:
	uvicorn kt.main:app --reload --host 0.0.0.0 --port 8000

run:
	uvicorn kt.main:app --host 0.0.0.0 --port 8000

test:
	pytest -q

lint:
	ruff check src tests

fmt:
	ruff format src tests

typecheck:
	mypy src

docker:
	docker compose up --build

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache build dist *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} +

smoke-aurora:
	$(PY) -m scripts.smoke_aurora

smoke-moonboard:
	$(PY) -m scripts.smoke_moonboard
