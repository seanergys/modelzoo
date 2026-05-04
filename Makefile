# seanergys-modelzoo Makefile
# Run `make help` for usage

.PHONY: help venv install install-ci install-hooks sample-data \
        test test-unit test-smoke test-smoke-full test-datasets test-integration test-pipeline test-all \
        lint format format-check typecheck audit check-secrets pre-push ci \
        coverage clean clean-venv clean-fixtures clean-all

VENV ?= .venv
PYTHON ?= $(VENV)/bin/python
PYTEST ?= $(VENV)/bin/pytest
export PYTHONPATH := $(shell pwd):$(PYTHONPATH)

# -----------------------------------------------------------------------------
# Help
# -----------------------------------------------------------------------------
help:
	@echo ""
	@echo "seanergys-modelzoo — available commands"
	@echo "========================================"
	@echo ""
	@echo "┌─────────────────────────────────────────────────────────┐"
	@echo "│  BEFORE YOU PUSH — run these steps every time:         │"
	@echo "│                                                         │"
	@echo "│  1. make format       Auto-fix code style              │"
	@echo "│  2. make pre-push     Lint + secrets + fast tests      │"
	@echo "│                                                         │"
	@echo "│  One-time setup: make install-hooks                    │"
	@echo "│  (runs pre-push automatically on every git push)       │"
	@echo "└─────────────────────────────────────────────────────────┘"
	@echo ""
	@echo "Setup (run once after cloning):"
	@echo "  make venv            Create .venv virtual environment"
	@echo "  make install         Create .venv + install dev dependencies"
	@echo "  make install-ci      Create .venv + install all deps including ML libs"
	@echo "  make install-hooks   Install git pre-push hook (auto-runs make pre-push)"
	@echo "  make sample-data     Download small fixture files from Zenodo → tests/fixtures/"
	@echo ""
	@echo "Before every push:"
	@echo "  make format          Auto-fix code formatting (run this first)"
	@echo "  make format-check    Check formatting without modifying files"
	@echo "  make pre-push        Full pre-push gate: format-check + lint + secrets + tests"
	@echo ""
	@echo "Tests:"
	@echo "  make test            Unit + smoke (fast, no network needed)"
	@echo "  make test-unit       Unit tests + terminal coverage — tests/unit/"
	@echo "  make test-smoke      Smoke tests, no network (skips Zenodo)"
	@echo "  make test-smoke-full Smoke tests including Zenodo (needs network)"
	@echo "  make test-datasets   Dataset load tests (needs sample-data or network)"
	@echo "  make test-pipeline   Integration: full train→predict→save→load per model"
	@echo "  make test-integration All integration tests — tests/integration/"
	@echo "  make test-all        Everything — unit + smoke + integration"
	@echo ""
	@echo "Code quality:"
	@echo "  make lint            Ruff lint check"
	@echo "  make typecheck       Mypy type check (informational, non-blocking)"
	@echo "  make coverage        Unit tests + XML/HTML/terminal coverage report"
	@echo "  make audit           Dependency vulnerability scan (pip-audit)"
	@echo "  make check-secrets   Scan for secrets in code"
	@echo ""
	@echo "CI simulation:"
	@echo "  make ci              Run everything exactly as GitLab CI does"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean           Remove caches and build artifacts"
	@echo "  make clean-venv      Remove .venv/ (re-run 'make venv' to recreate)"
	@echo "  make clean-fixtures  Remove fixture parquet files (forces re-download)"
	@echo "  make clean-all       clean + clean-venv + clean-fixtures"
	@echo ""
	@echo "Options:"
	@echo "  CI_SKIP_ZENODO=1 make test-datasets    Skip Zenodo, use local fixtures only"
	@echo "  SAMPLE_MAX_ROWS=50 make sample-data    Limit rows per fixture (default: 100)"
	@echo ""

# -----------------------------------------------------------------------------
# Setup
# -----------------------------------------------------------------------------

# Real file target — Make skips creation if .venv/ already exists
$(VENV):
	@echo "→ Creating virtual environment in $(VENV)/..."
	python3 -m venv $(VENV)
	$(VENV)/bin/pip install --upgrade pip --quiet
	@echo "✓ Virtual environment ready — activate with: source $(VENV)/bin/activate"

venv: $(VENV)

install: $(VENV)
	poetry config virtualenvs.in-project true
	poetry install --with dev

install-ci: $(VENV)
	poetry config virtualenvs.in-project true
	poetry install --with dev,ci

# -----------------------------------------------------------------------------
# Sample data (needed for integration and dataset load tests)
# -----------------------------------------------------------------------------
sample-data:
	@echo "→ Downloading sample fixtures from Zenodo..."
	poetry install -q --with ci 2>/dev/null || true
	$(PYTHON) scripts/create_sample_data.py $(ARGS)
	@echo "✓ Sample data created in tests/fixtures/sample_data/"

# -----------------------------------------------------------------------------
# Tests
# -----------------------------------------------------------------------------

# Fast: unit + smoke (no network, no ML training — run before every push)
test: test-unit test-smoke
	@echo ""
	@echo "✓ All fast tests passed"

test-unit:
	@echo "→ Running unit tests..."
	mkdir -p coverage
	$(PYTEST) tests/unit/ -v \
	    --cov=seanergys_modelzoo \
	    --cov-report=xml:coverage/cobertura-coverage.xml \
	    --cov-report=term-missing

test-smoke:
	@echo "→ Running smoke tests (no network — Approach A contract checks, model discovery)..."
	$(PYTEST) tests/smoke/ -v -m "not zenodo"

test-smoke-full:
	@echo "→ Running all smoke tests including Zenodo/network (Approach B dataset loading)..."
	@echo "  Note: requires network. Approach B tests download a small subset from Zenodo."
	$(PYTEST) tests/smoke/ -v

# Dataset load tests — uses local fixtures or Zenodo
test-datasets:
	@echo "→ Running dataset load tests..."
	@echo "  (Run 'make sample-data' first for local fixtures)"
	$(PYTEST) tests/smoke/test_datasets_load.py -v

# Full pipeline: train → predict → save → load for each discovered model
test-pipeline:
	@echo "→ Running model pipeline integration tests..."
	@echo "  (Run 'make sample-data' first)"
	$(PYTEST) tests/integration/test_model_pipeline.py -v -s

# All integration tests
test-integration:
	@echo "→ Running all integration tests..."
	@echo "  (Run 'make sample-data' first)"
	$(PYTEST) tests/integration/ -v -s

# Everything
test-all: test-unit test-smoke test-datasets test-integration
	@echo ""
	@echo "✓ All tests passed"

# -----------------------------------------------------------------------------
# Code quality
# -----------------------------------------------------------------------------
lint:
	@echo "→ Running ruff lint..."
	$(PYTHON) -m ruff check seanergys_modelzoo ci tests

format:
	@echo "→ Running ruff format..."
	$(PYTHON) -m ruff format seanergys_modelzoo ci tests

format-check:
	@echo "→ Checking code formatting (no changes made)..."
	$(PYTHON) -m ruff format --check seanergys_modelzoo ci tests

typecheck:
	@echo "→ Running mypy..."
	$(PYTHON) -m pip install -q mypy types-PyYAML 2>/dev/null || true
	-$(PYTHON) -m mypy seanergys_modelzoo ci tests --ignore-missing-imports --explicit-package-bases

coverage:
	@echo "→ Running unit tests with coverage report..."
	mkdir -p coverage
	$(PYTEST) tests/unit/ -v \
	    --cov=seanergys_modelzoo \
	    --cov-report=xml:coverage/cobertura-coverage.xml \
	    --cov-report=html:coverage/html \
	    --cov-report=term-missing
	@echo "✓ HTML report: coverage/html/index.html"

audit:
	@echo "→ Running dependency vulnerability scan..."
	$(PYTHON) -m pip install -q pip-audit poetry-plugin-export 2>/dev/null || true
	poetry export -f requirements.txt --without-hashes --with dev,ci -o /tmp/poetry-audit-reqs.txt
	$(PYTHON) -m pip_audit -r /tmp/poetry-audit-reqs.txt

check-secrets:
	@chmod +x ci/check_secrets.sh 2>/dev/null || true
	@./ci/check_secrets.sh .

# -----------------------------------------------------------------------------
# Pre-push gate — fast checks that must pass before git push
# -----------------------------------------------------------------------------

# Installs a git hook so 'git push' runs pre-push automatically
install-hooks:
	@echo "→ Installing git pre-push hook..."
	@printf '#!/bin/sh\nexec make pre-push\n' > .git/hooks/pre-push
	@chmod +x .git/hooks/pre-push
	@echo "✓ Hook installed — 'make pre-push' will run automatically on every git push"

pre-push: format-check check-secrets lint test
	@echo ""
	@echo "✓ Pre-push checks passed — safe to push"

# -----------------------------------------------------------------------------
# CI simulation — mirrors GitLab pipeline exactly
# -----------------------------------------------------------------------------
ci:
	@echo ""
	@echo "════════════════════════════════════════"
	@echo " Simulating GitLab CI pipeline locally"
	@echo "════════════════════════════════════════"
	@echo ""
	@echo "── Stage 1: sanity ──"
	find seanergys_modelzoo ci tests -name "*.py" -print0 | xargs -0 $(PYTHON) -m py_compile && echo "✓ syntax OK"
	test -f pyproject.toml && test -d seanergys_modelzoo && test -d ci && test -d tests && echo "✓ structure OK"
	@echo ""
	@echo "── Stage 2: validate ──"
	$(PYTHON) ci/validate_yaml.py && echo "✓ YAML OK"
	@echo ""
	@echo "── Stage 3: lint ──"
	-$(PYTHON) -m ruff check seanergys_modelzoo ci tests
	-$(PYTHON) -m ruff format --check seanergys_modelzoo ci tests
	-$(PYTHON) -m mypy seanergys_modelzoo ci tests --ignore-missing-imports --explicit-package-bases
	@echo ""
	@echo "── Stage 4: test ──"
	mkdir -p coverage
	$(PYTEST) tests/unit/ -v \
	    --cov=seanergys_modelzoo \
	    --cov-report=xml:coverage/cobertura-coverage.xml \
	    --cov-report=term-missing
	$(PYTEST) tests/smoke/test_models_smoke.py -v
	CI_SKIP_ZENODO=1 $(PYTEST) tests/smoke/test_datasets_smoke.py -v -m "not zenodo"
	CI_SKIP_ZENODO=1 $(PYTEST) tests/integration/ -v
	@echo ""
	@echo "✓ CI simulation complete"

# -----------------------------------------------------------------------------
# Clean
# -----------------------------------------------------------------------------
clean:
	rm -rf .pytest_cache .ruff_cache build/ dist/ *.egg-info coverage/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@echo "✓ Cleaned caches and build artifacts"

clean-venv:
	rm -rf $(VENV)
	@echo "✓ Removed $(VENV)/ — run 'make venv' or 'make install' to recreate"

clean-fixtures:
	rm -rf tests/fixtures/sample_data/
	@echo "✓ Cleared fixture files (run 'make sample-data' to recreate)"

clean-all: clean clean-venv clean-fixtures
	@echo "✓ Cleaned everything"
