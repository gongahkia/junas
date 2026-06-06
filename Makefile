.PHONY: up down dev api frontend test lint migrate ingest-all ingest-pdpc ingest-pdpc-guidelines ingest-sso ingest-mom ingest-commonlii-sg build-sglb-02 build-sglb-05 build-sglb-06 build-sglb-07 download-data setup eval eval-list synth-gen mcp

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

# === mcp server (issue #48) ===
# Usage: make mcp [MCP_HTTP=1]
# Invoked from repo root so the local backend.mcp package does not shadow the SDK's top-level `mcp`.
MCP_HTTP_ARG := $(if $(strip $(MCP_HTTP)),--http,)
MCP_PYTHON ?= .venv/bin/python
mcp:
	$(MCP_PYTHON) -m backend.mcp.server $(MCP_HTTP_ARG)

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
BACKEND_PYTHON ?= ../.venv/bin/python

ingest-all:
	cd backend && python -m ml.pipelines.run_all
	$(MAKE) ingest-mom
	$(MAKE) ingest-commonlii-sg

# SGLB-01: PDPC enforcement decisions → JSONL splits + harness YAML.
ingest-pdpc:
	cd backend && python -m data.ingestion.pdpc

# SGLB-14: PDPC Advisory Guidelines PDFs → JSONL corpus.
ingest-pdpc-guidelines:
	cd backend && python -m data.ingestion.pdpc_guidelines

# SSO statutes scrape: writes JSONL to vendor-data/sso/statutes.jsonl
# Usage: make ingest-sso [FORCE=1] [SSO_OUTPUT=path] [SSO_CODE=PDPA2012]
SSO_OUTPUT ?= vendor-data/sso/statutes.jsonl
SSO_CODE ?=
SSO_FORCE_ARG := $(if $(strip $(FORCE)),--force,)
SSO_CODE_ARG := $(if $(strip $(SSO_CODE)),--code $(SSO_CODE),)
ingest-sso:
	cd backend && python -m data.ingestion.sso --output $(SSO_OUTPUT) $(SSO_FORCE_ARG) $(SSO_CODE_ARG)

# SGLB-05: MOM enforcement/guidance network payloads.
# Dry-run by default for network safety. Use LIVE=1 after approval.
MOM_OUTPUT ?= vendor-data/mom/enforcement.jsonl
MOM_FORCE_ARG := $(if $(strip $(FORCE)),--force,)
MOM_LIVE_ARG := $(if $(strip $(LIVE)),--live,--dry-run)
ingest-mom:
	cd backend && ../.venv/bin/python -m data.ingestion.mom --output $(MOM_OUTPUT) $(MOM_FORCE_ARG) $(MOM_LIVE_ARG)

# SGLB-07: CommonLII SG cases scrape; writes JSONL to vendor-data/sg_cases/judgments.jsonl
# Usage: make ingest-commonlii-sg [COMMONLII_SG_COURT=SGCA] [COMMONLII_SG_YEAR=2024] [COMMONLII_SG_LIMIT=25] [DRY_RUN=1] [FORCE=1]
COMMONLII_SG_OUTPUT ?= vendor-data/sg_cases/judgments.jsonl
COMMONLII_SG_COURT ?=
COMMONLII_SG_YEAR ?=
COMMONLII_SG_LIMIT ?=
COMMONLII_SG_COURT_ARG := $(if $(strip $(COMMONLII_SG_COURT)),--court $(COMMONLII_SG_COURT),)
COMMONLII_SG_YEAR_ARG := $(if $(strip $(COMMONLII_SG_YEAR)),--year $(COMMONLII_SG_YEAR),)
COMMONLII_SG_LIMIT_ARG := $(if $(strip $(COMMONLII_SG_LIMIT)),--limit $(COMMONLII_SG_LIMIT),)
COMMONLII_SG_DRY_RUN_ARG := $(if $(strip $(DRY_RUN)),--dry-run,)
COMMONLII_SG_FORCE_ARG := $(if $(strip $(FORCE)),--force,)
ingest-commonlii-sg:
	cd backend && $(BACKEND_PYTHON) -m data.ingestion.commonlii_sg --output $(COMMONLII_SG_OUTPUT) $(COMMONLII_SG_COURT_ARG) $(COMMONLII_SG_YEAR_ARG) $(COMMONLII_SG_LIMIT_ARG) $(COMMONLII_SG_DRY_RUN_ARG) $(COMMONLII_SG_FORCE_ARG)

# SGLB-02: build statute-QA dataset from the SSO JSONL.
build-sglb-02:
	cd backend && python -m benchmark.dataset_builders.sglb_02

# SGLB-05: build Employment-Issue dataset from the MOM JSONL.
# Requires the MOM scraper (#59) to have populated vendor-data/mom/enforcement.jsonl.
build-sglb-05:
	cd backend && python -m benchmark.dataset_builders.sglb_05

# SGLB-06: build ROC 2021 dataset from the SSO JSONL.
# Requires `make ingest-sso SSO_CODE=ROC2021` to have run first.
build-sglb-06:
	cd backend && python -m benchmark.dataset_builders.sglb_06

# SGLB-07: build Jurisdiction-Routing dataset from CommonLII SG cases.
# Requires the SG case ingester (#34) to have run first.
build-sglb-07:
	cd backend && python -m benchmark.dataset_builders.sglb_07

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
