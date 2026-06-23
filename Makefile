.DEFAULT_GOAL := help

# ── Variables ─────────────────────────────────────────────────────────────────
COMPOSE         := docker compose
API_DIR         := services/api
CONSUMER_DIR    := services/consumer
SCORING_DIR     := services/scoring
DISCOVERY_DIR   := services/discovery
MIGRATION_DIR   := infra/migrations
DB_URL          ?= ******localhost:5432/betman_data

.PHONY: help install api-dev consumer-dev scoring-dev discovery-dev \
        migrate migrate-002 docker-up docker-down docker-infra docker-logs docker-build \
        test lint format status clean

# ── Help ──────────────────────────────────────────────────────────────────────
help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-22s\033[0m %s\n", $$1, $$2}'

# ── Local Development ─────────────────────────────────────────────────────────
install: ## Install all Python dependencies for every service
	pip install -e "$(API_DIR)[dev]"
	pip install -e "$(CONSUMER_DIR)[dev]"
	pip install -e "$(SCORING_DIR)[dev]"
	pip install -e "$(DISCOVERY_DIR)[dev]"

api-dev: ## Run API service locally with hot reload
	cd $(API_DIR) && uvicorn app.main:app --reload --port 8000

consumer-dev: ## Run Consumer service locally
	cd $(CONSUMER_DIR) && python -m app.main

scoring-dev: ## Run Scoring service locally
	cd $(SCORING_DIR) && python -m app.main

discovery-dev: ## Run Discovery service locally
	cd $(DISCOVERY_DIR) && python -m app.main

# ── Database ──────────────────────────────────────────────────────────────────
migrate: ## Apply all migrations (001 + 002 + 003) to the target DB
	psql "$(DB_URL)" -f $(MIGRATION_DIR)/001_initial_schema.sql
	psql "$(DB_URL)" -f $(MIGRATION_DIR)/002_intelligence_layers.sql
	psql "$(DB_URL)" -f $(MIGRATION_DIR)/003_pedigree_and_providers.sql

migrate-001: ## Apply only the initial schema migration
	psql "$(DB_URL)" -f $(MIGRATION_DIR)/001_initial_schema.sql

migrate-002: ## Apply only the intelligence layers migration
	psql "$(DB_URL)" -f $(MIGRATION_DIR)/002_intelligence_layers.sql

# ── Docker ────────────────────────────────────────────────────────────────────
docker-infra: ## Start only infrastructure services (postgres, redis, minio)
	$(COMPOSE) up -d postgres redis minio minio-init

docker-up: ## Start all services (infra + app)
	$(COMPOSE) up -d

docker-down: ## Stop all running containers
	$(COMPOSE) down

docker-build: ## Rebuild all Docker images
	$(COMPOSE) build

docker-logs: ## Follow logs for all containers
	$(COMPOSE) logs -f

docker-logs-api: ## Follow API service logs
	$(COMPOSE) logs -f api

docker-logs-consumer: ## Follow Consumer service logs
	$(COMPOSE) logs -f consumer

# ── Testing ───────────────────────────────────────────────────────────────────
test: ## Run all tests
	pytest tests/ -v

test-api: ## Run API service tests only
	pytest tests/api/ -v

test-consumer: ## Run Consumer service tests only
	pytest tests/consumer/ -v

# ── Linting and Formatting ────────────────────────────────────────────────────
lint: ## Run ruff linter across all services
	ruff check services/ libs/

format: ## Auto-format all Python code with ruff
	ruff format services/ libs/

# ── Status ────────────────────────────────────────────────────────────────────
status: ## Show health of running local services
	@echo "=== Docker Containers ==="
	@$(COMPOSE) ps
	@echo ""
	@echo "=== API Health ==="
	@curl -s http://localhost:8000/v1/health | python3 -m json.tool || echo "API not reachable"

# ── Clean ─────────────────────────────────────────────────────────────────────
clean: ## Remove Python caches and build artifacts
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
