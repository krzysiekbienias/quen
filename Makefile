# Recipes start with ">" instead of a TAB, so the file survives copy-paste.
.RECIPEPREFIX = >
-include .env
export

.PHONY: help install fmt lint types contracts test test-int check explore

help: ## list available targets
> @grep -E '^[a-z-]+:.*## ' Makefile | awk 'BEGIN {FS = ":.*## "} {printf "  %-10s %s\n", $$1, $$2}'

install: ## create .venv and install dependencies
> uv sync

fmt: ## format code
> uv run ruff format .

lint: ## lint code
> uv run ruff check .

types: ## strict type checking
> uv run mypy

contracts: ## check layer contracts
> uv run lint-imports

test: ## unit tests (no real database needed)
> uv run pytest -m "not integration"

test-int: ## integration tests on the real database (QUEN_DB_PATH in .env)
> uv run pytest -m integration

check: fmt lint types contracts test ## everything to run before a commit

explore: ## peek at the market data
> uv run python scripts/explore_data.py