# Python Software Factory — Root Makefile
# Orchestrates infrastructure, builds, and project deployment.

.PHONY: help dev stop build test lint check

PROJECT ?= companion_x

help:
	@echo "Factory Commands:"
	@echo "  make dev          - Start infra services (postgres, redis, neo4j, etc.)"
	@echo "  make stop         - Stop all services"
	@echo "  make build        - Build Docker image for PROJECT (default: companion_x)"
	@echo "  make up           - Start full stack (infra + app) for PROJECT"
	@echo "  make test         - Run all tests"
	@echo "  make test-project - Run tests for PROJECT"
	@echo "  make lint         - Run ruff linter"
	@echo "  make check        - Run guardian compliance check"
	@echo ""
	@echo "Override project: make up PROJECT=flet_dashboard"

# --- Infrastructure ---

dev:
	docker compose up -d postgres redis neo4j keycloak chromadb seaweedfs phoenix dagster

stop:
	docker compose -f projects/$(PROJECT)/docker-compose.yml down 2>/dev/null || true
	docker compose down 2>/dev/null || true

# --- Build ---

build:
	docker compose -f projects/$(PROJECT)/docker-compose.yml build

# --- Run (full stack) ---
# Project compose is self-contained (includes its own infra services).
# No need to start root infra first — that causes port conflicts.

up:
	docker compose -f projects/$(PROJECT)/docker-compose.yml up -d

# --- Quality ---

test:
	uv run pytest

test-project:
	uv run pytest components/*/test bases/*/test -v

lint:
	uv run ruff check components/ bases/ projects/ scripts/

check:
	uv run python -c "from factory.foreman.interface import guardian_check; print(guardian_check())"
