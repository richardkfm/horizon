# horizon — common developer and packaging tasks.
# Run `make help` for the list.

.DEFAULT_GOAL := help
PY ?= python3
VENV := .venv
BIN := $(VENV)/bin

.PHONY: help venv install dev run test lint fmt build docker compose-check clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "} {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

venv: ## Create the virtualenv
	$(PY) -m venv $(VENV)

install: venv ## Install horizon (runtime only)
	$(BIN)/pip install --upgrade pip
	$(BIN)/pip install .

dev: venv ## Install horizon with dev dependencies
	$(BIN)/pip install --upgrade pip
	$(BIN)/pip install -e .[dev]

run: ## Run the dev server with autoreload
	$(BIN)/uvicorn horizon.main:app --reload --host 0.0.0.0 --port 8080

test: ## Run the test suite
	$(BIN)/pytest

lint: ## Lint with ruff
	$(BIN)/ruff check .

fmt: ## Format with ruff
	$(BIN)/ruff format .

build: ## Build a wheel + sdist into dist/
	$(BIN)/pip install --upgrade build
	$(BIN)/python -m build

docker: ## Build the Docker image
	docker build -t horizon:$(shell $(PY) -c "import tomllib;print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])") .

compose-check: ## Validate the docker compose file
	docker compose config

clean: ## Remove build artifacts and caches
	rm -rf dist build *.egg-info .pytest_cache
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
