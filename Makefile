SHELL := /bin/bash

ROOT_DIR := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
API_DIR := $(ROOT_DIR)/api
WEB_DIR := $(ROOT_DIR)/kilter-together-app

API_PORT ?= 8082
WEB_PORT ?= 5173
WEB_HOST ?= 0.0.0.0

DEV_APP_SECRET ?= development-room-secret
DEV_ENCRYPTION_KEY ?= MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=
DEV_SECURE_COOKIES ?= false

.PHONY: help install web-install bootstrap dev dev-api dev-web docker-bootstrap docker-up docker-down docker-logs docker-production-render docker-production-bootstrap docker-production-up test lint build check health

help: ## Show available commands
	@awk 'BEGIN {FS = ":.*##"; print "Available targets:"} /^[a-zA-Z0-9_.-]+:.*##/ {printf "  %-14s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install: web-install ## Install local development dependencies

web-install: ## Install frontend dependencies
	cd "$(WEB_DIR)" && npm ci

bootstrap: ## Download or refresh the local Kilter dataset and images
	cd "$(API_DIR)" && \
	KILTER_TOGETHER_APP_SECRET="$(DEV_APP_SECRET)" \
	KILTER_TOGETHER_ENCRYPTION_KEY="$(DEV_ENCRYPTION_KEY)" \
	KILTER_TOGETHER_PORT="$(API_PORT)" \
	go run . bootstrap

dev: ## Run the API and web app together for local development
	@set -euo pipefail; \
	trap 'kill $$API_PID $$WEB_PID 2>/dev/null || true' EXIT INT TERM; \
	echo "Starting API on http://localhost:$(API_PORT)"; \
	( \
		cd "$(API_DIR)" && \
		KILTER_TOGETHER_APP_SECRET="$(DEV_APP_SECRET)" \
		KILTER_TOGETHER_ENCRYPTION_KEY="$(DEV_ENCRYPTION_KEY)" \
		KILTER_TOGETHER_SECURE_COOKIES="$(DEV_SECURE_COOKIES)" \
		KILTER_TOGETHER_PORT="$(API_PORT)" \
		go run . serve --bootstrap-if-missing \
	) & \
	API_PID=$$!; \
	echo "Starting web on http://localhost:$(WEB_PORT)"; \
	( \
		cd "$(WEB_DIR)" && \
		npm run dev -- --host "$(WEB_HOST)" --port "$(WEB_PORT)" \
	) & \
	WEB_PID=$$!; \
	wait

dev-api: ## Run only the API locally with development secrets
	cd "$(API_DIR)" && \
	KILTER_TOGETHER_APP_SECRET="$(DEV_APP_SECRET)" \
	KILTER_TOGETHER_ENCRYPTION_KEY="$(DEV_ENCRYPTION_KEY)" \
	KILTER_TOGETHER_SECURE_COOKIES="$(DEV_SECURE_COOKIES)" \
	KILTER_TOGETHER_PORT="$(API_PORT)" \
	go run . serve --bootstrap-if-missing

dev-web: ## Run only the web app locally
	cd "$(WEB_DIR)" && npm run dev -- --host "$(WEB_HOST)" --port "$(WEB_PORT)"

docker-up: ## Build and run the Docker stack after docker-bootstrap has seeded /data
	cd "$(ROOT_DIR)" && docker compose up --build

docker-bootstrap: ## Bootstrap the shared Docker data volume before docker-up
	cd "$(ROOT_DIR)" && docker compose --profile bootstrap run --rm kilter-together-bootstrap

docker-down: ## Stop the Docker stack
	cd "$(ROOT_DIR)" && docker compose down

docker-logs: ## Tail Docker compose logs
	cd "$(ROOT_DIR)" && docker compose logs -f

docker-production-render: ## Render the production Caddyfile from compose.production.env
	cd "$(ROOT_DIR)" && ./scripts/render-caddyfile.sh

docker-production-bootstrap: docker-production-render ## Bootstrap the production data volume
	cd "$(ROOT_DIR)" && docker compose --env-file compose.production.env -f docker-compose.production.yml --profile bootstrap run --rm kilter-together-bootstrap

docker-production-up: docker-production-render ## Build and run the production compose stack
	cd "$(ROOT_DIR)" && docker compose --env-file compose.production.env -f docker-compose.production.yml up -d --build

test: ## Run backend and frontend tests
	cd "$(API_DIR)" && go test ./...
	cd "$(WEB_DIR)" && npm run test -- --run

lint: ## Run frontend lint checks
	cd "$(WEB_DIR)" && npm run lint

build: ## Build backend and frontend artifacts
	cd "$(API_DIR)" && go build ./...
	cd "$(WEB_DIR)" && npm run build

check: test lint build ## Run the full local verification suite

health: ## Check the running API health endpoint
	@curl --fail --silent --show-error "http://localhost:$(API_PORT)/api/healthz" && echo
