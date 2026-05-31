# Developer convenience targets. See README.md.
COMPOSE = docker compose -f infra/compose/docker-compose.yml

.PHONY: env up down logs build backend-test backend-lint frontend-build

env: ## Create backend/.env from the example (no-op if it exists)
	@test -f backend/.env || cp backend/.env.example backend/.env

up: env ## Start the full local stack
	$(COMPOSE) up --build

down: ## Stop the stack and remove volumes
	$(COMPOSE) down -v

logs: ## Tail logs
	$(COMPOSE) logs -f

build: ## Build all images
	$(COMPOSE) build

backend-test: ## Run backend tests
	cd backend && pytest -q

backend-lint: ## Lint backend
	cd backend && ruff check app alembic tests

frontend-build: ## Build frontend
	cd frontend && npm install && npm run build
