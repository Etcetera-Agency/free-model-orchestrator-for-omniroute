.DEFAULT_GOAL := help
PY := .venv/bin/python
VENV := .venv/bin

.PHONY: help install lint format fmt typecheck deadcode test check fix analysis

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

install: ## Install package + dev toolchain into .venv
	$(PY) -m pip install -e '.[dev]'

lint: ## Ruff lint (no changes)
	ruff check src tests

format: ## Ruff format check (no changes)
	ruff format --check src tests

typecheck: ## Pyright static type check (src)
	pyright

deadcode: ## Vulture dead-code scan (>=80% confidence)
	vulture src whitelist.py

test: ## Run the pytest suite
	$(VENV)/pytest -q

check: lint format typecheck deadcode ## Run every static gate (no mutation)

fix: ## Auto-apply ruff lint fixes + formatting
	ruff check --fix src tests
	ruff format src tests

analysis: ## Print a one-screen health snapshot
	@echo "== ruff =="      ; ruff check src tests --statistics 2>&1 | tail -n +1 || true
	@echo "== format =="    ; ruff format --check src tests 2>&1 | tail -1 || true
	@echo "== pyright =="   ; pyright 2>&1 | tail -1 || true
	@echo "== deadcode =="  ; vulture src whitelist.py 2>&1 || echo "clean"
