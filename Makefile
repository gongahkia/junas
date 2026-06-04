.PHONY: up down dev api frontend test lint migrate ingest-all ingest-pdpc download-data setup eval eval-list synth-gen

# === primary ===
up:
	docker compose up -d

down:
	docker compose down

dev:
	@echo "Starting dev servers (backend :8000, frontend :3000)..."
	$(MAKE) -j2 api frontend

# === backend ===
api:
	cd backend && uvicorn api.main:app --reload --port 8000

# === frontend ===
frontend:
	cd frontend && npm run dev

# === database ===
migrate:
	cd backend && alembic -c migrations/alembic.ini upgrade head

# === testing ===
test:
	cd backend && pytest -x -q

lint:
	cd backend && ruff check . && mypy api ml data

# === benchmarks (SG-LegalBench) ===
eval-list:
	cd backend && python3 -m benchmark.cli list

# Usage: make eval WORKFLOW=echo DATASET=benchmark/datasets/example_echo.yaml EVALUATORS="citation_format_valid cites_sg_statute"
WORKFLOW ?= echo
DATASET ?= benchmark/datasets/example_echo.yaml
EVALUATORS ?= citation_format_valid
eval:
	cd backend && python3 -m benchmark.cli run \
	  --workflow $(WORKFLOW) \
	  --dataset $(DATASET) \
	  $(addprefix --evaluator ,$(EVALUATORS))

# Usage: make synth-gen TASK=sglb_08 N=50 PROVIDERS="anthropic,openai,google" MAX_COST_USD=5
# Dry run: make synth-gen TASK=sglb_08 N=20 DRY_RUN=1
TASK ?= sglb_08
N ?= 50
PROVIDERS ?= anthropic,openai,google
SEED ?= 0
DRY_RUN ?=
MAX_COST_USD ?=
ENV_FILE ?=
NO_ENV_FILE ?=
SYNTH_EXTRA_ARGS :=
ifneq ($(strip $(DRY_RUN)),)
SYNTH_EXTRA_ARGS += --dry-run
endif
ifneq ($(strip $(MAX_COST_USD)),)
SYNTH_EXTRA_ARGS += --max-cost-usd $(MAX_COST_USD)
endif
ifneq ($(strip $(ENV_FILE)),)
SYNTH_EXTRA_ARGS += --env-file $(ENV_FILE)
endif
ifneq ($(strip $(NO_ENV_FILE)),)
SYNTH_EXTRA_ARGS += --no-env-file
endif
synth-gen:
	cd backend && python3 -m benchmark.synthetic generate \
	  --task $(TASK) \
	  --n $(N) \
	  --providers $(PROVIDERS) \
	  --seed $(SEED) \
	  $(SYNTH_EXTRA_ARGS)

# === data ===
ingest-all:
	cd backend && python -m ml.pipelines.run_all

# SGLB-01: PDPC enforcement decisions → JSONL splits + harness YAML.
ingest-pdpc:
	cd backend && python -m data.ingestion.pdpc

VENDOR_DIR := vendor-data

download-data: download-lecard download-glossaries download-ner
	@echo "All datasets downloaded to $(VENDOR_DIR)/"

download-lecard:
	@mkdir -p $(VENDOR_DIR)
	@if [ ! -d "$(VENDOR_DIR)/LeCaRD" ]; then git clone --depth 1 https://github.com/myx666/LeCaRD.git $(VENDOR_DIR)/LeCaRD; fi

download-glossaries:
	@mkdir -p $(VENDOR_DIR)
	@if [ ! -d "$(VENDOR_DIR)/datasets" ]; then git clone --depth 1 https://github.com/public-law/datasets.git $(VENDOR_DIR)/datasets; fi

download-ner:
	@mkdir -p $(VENDOR_DIR)
	@if [ ! -d "$(VENDOR_DIR)/Legal-Entity-Recognition" ]; then git clone --depth 1 https://github.com/elenanereiss/Legal-Entity-Recognition.git $(VENDOR_DIR)/Legal-Entity-Recognition; fi

# === quick setup ===
setup: download-data
	docker compose up -d postgres elasticsearch qdrant redis
	sleep 5
	$(MAKE) migrate
	$(MAKE) ingest-all
	@echo "Setup complete. Run 'make up' to start all services."
