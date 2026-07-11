# seanergys-modelzoo Makefile
# Run `make help` for usage

.PHONY: help venv install install-ci install-hooks sample-data \
        lock deps-check \
        test test-unit test-smoke-models test-smoke-data test-integration test-pipeline test-all test-wheel \
        lint format format-check typecheck audit check-secrets pre-push ci \
        docs-ci docs-ci-check \
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
	@echo "│  3. make ci           FULL local mirror of GitLab CI   │"
	@echo "│                       (run this last — if it's green,  │"
	@echo "│                        the GitLab pipeline will be too)│"
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
	@echo "Dependencies (poetry.lock <-> pyproject.toml):"
	@echo "  make deps-check      Verify poetry.lock is in sync (runs before every test)"
	@echo "  make lock            Regenerate poetry.lock after editing pyproject.toml"
	@echo ""
	@echo "Before every push:"
	@echo "  make format          Auto-fix code formatting (run this first)"
	@echo "  make format-check    Check formatting without modifying files"
	@echo "  make pre-push        Full pre-push gate: format-check + lint + secrets + tests"
	@echo ""
	@echo "Tests:"
	@echo "  make test                Unit + smoke tests (fast, no data loading)"
	@echo "  make test-unit           Unit tests + terminal coverage — tests/unit/"
	@echo "  make test-smoke-models   Model smoke tests (discovery, instantiation, no data)"
	@echo "  make test-smoke-data     Data smoke tests (fixture loading, no Zenodo)"
	@echo "  make test-integration    Full integration tests — tests/integration/"
	@echo "  make test-all            Everything — unit + smoke + integration"
	@echo "  make test-wheel          Build wheel + verify it installs and imports"
	@echo ""
	@echo "Code quality:"
	@echo "  make lint            Ruff lint check"
	@echo "  make typecheck       Mypy type check (informational, non-blocking)"
	@echo "  make coverage        Unit tests + XML/HTML/terminal coverage report"
	@echo "  make audit           Dependency vulnerability scan (pip-audit)"
	@echo "  make check-secrets   Scan for secrets in code"
	@echo ""
	@echo "Docs (auto-generated CI capability tables):"
	@echo "  make docs-ci         Regenerate docs/ci-cd.md from .gitlab-ci.yml + code + policy"
	@echo "  make docs-ci-check   Fail if docs/ci-cd.md is stale (used by make ci)"
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
# Dependencies — keep poetry.lock in sync with pyproject.toml
#
# GitLab CI runs `poetry install`, which under Poetry 2.x ABORTS if the lock is
# stale ("pyproject.toml changed significantly since poetry.lock was last
# generated"). That fails EVERY test job before a single test runs. deps-check
# catches that here in ~1 s so you never push a stale lock. If it fails, run
# `make lock` and commit both pyproject.toml and poetry.lock together.
# -----------------------------------------------------------------------------
deps-check:
	@echo "→ Verifying poetry.lock is in sync with pyproject.toml..."
	@poetry check --lock || { \
	    echo ""; \
	    echo "✗ poetry.lock is OUT OF SYNC with pyproject.toml."; \
	    echo "  Run 'make lock' and commit both files, then retry."; \
	    exit 1; \
	}
	@echo "✓ poetry.lock in sync with pyproject.toml"

lock:
	@echo "→ Regenerating poetry.lock from pyproject.toml..."
	poetry lock
	@echo "✓ poetry.lock regenerated — commit it ALONGSIDE pyproject.toml"

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

# Fast: unit + smoke tests (no network, no data loading — run before every push)
test: test-unit test-smoke-models test-smoke-data
	@echo ""
	@echo "✓ All fast tests passed"

test-unit: deps-check
	@echo "→ Running unit tests..."
	mkdir -p coverage
	$(PYTEST) tests/unit/ -v \
	    --cov=seanergys_modelzoo \
	    --cov-report=xml:coverage/cobertura-coverage.xml \
	    --cov-report=term-missing

test-smoke-models: deps-check
	@echo "→ Running model smoke tests (discovery, instantiation, no data loading)..."
	$(PYTEST) tests/smoke/test_smoke_models.py -v

test-smoke-data: deps-check
	@echo "→ Running data smoke tests (fixtures, no Zenodo download)..."
	@echo "  (Run 'make sample-data' first for local fixtures)"
	CI_SKIP_ZENODO=1 $(PYTEST) tests/smoke/test_smoke_data.py -v -m "not zenodo"

# Full pipeline: train → predict → save → load for each discovered model
test-pipeline: deps-check
	@echo "→ Running model pipeline integration tests..."
	@echo "  (Run 'make sample-data' first)"
	$(PYTEST) tests/integration/test_model_pipeline.py -v -s

# All integration tests
test-integration: deps-check
	@echo "→ Running all integration tests..."
	@echo "  (Run 'make sample-data' first)"
	$(PYTEST) tests/integration/ -v -s

# Everything
test-all: test-unit test-smoke-models test-smoke-data test-integration
	@echo ""
	@echo "✓ All tests passed"

# Build the wheel and verify it installs + imports with the source tree off the
# path — mirrors GitLab's build:wheel + test:wheel stages. Uses --no-deps so it
# reuses the already-installed ML stack instead of re-downloading torch, then
# uninstalls the wheel to leave .venv clean.
test-wheel:
	@echo "→ Building wheel (mirrors build:wheel)..."
	poetry build --format wheel
	@ls -lh dist/*.whl
	@echo "→ Verifying the built wheel installs and imports (mirrors test:wheel)..."
	$(PYTHON) -m pip install -q --force-reinstall --no-deps dist/*.whl
	PYTHONPATH= $(PYTHON) ci/verify_wheel.py
	$(PYTHON) -m pip uninstall -y -q seanergys-modelzoo
	@echo "✓ Wheel builds, installs, and imports cleanly"

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
# Docs — auto-generated CI capability & rules tables (docs/ci-cd.md)
# The tables are regenerated from .gitlab-ci.yml + the code + ci/policy.yml, so
# they never drift. On the default branch the docs:autogen CI job commits any
# regenerated changes automatically.
# -----------------------------------------------------------------------------
docs-ci:
	@echo "→ Regenerating docs/ci-cd.md from pipeline + code + policy..."
	$(PYTHON) ci/gen_capabilities_doc.py

docs-ci-check:
	@echo "→ Checking docs/ci-cd.md is up to date..."
	$(PYTHON) ci/gen_capabilities_doc.py --check

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
	@echo "→ Checking CI docs are current (non-blocking)..."
	-$(PYTHON) ci/gen_capabilities_doc.py --check
	@echo ""
	@echo "✓ Pre-push checks passed — safe to push"

# -----------------------------------------------------------------------------
# CI simulation — mirrors GitLab pipeline exactly
# -----------------------------------------------------------------------------
# Full local mirror of the GitLab pipeline:
#   deps → sanity → validate → lint → test → audit → build → test-wheel
# Hard-fails on anything GitLab marks allow_failure:false (deps, sanity,
# validate, tests, wheel). Steps GitLab marks allow_failure:true (lint, audit,
# secrets) are prefixed with '-' so they report but don't abort — exactly like
# the pipeline. If this is green, the GitLab run will be green too.
ci: deps-check
	@echo ""
	@echo "════════════════════════════════════════"
	@echo " Simulating GitLab CI pipeline locally"
	@echo "════════════════════════════════════════"
	@echo ""
	@echo "── Stage 0: deps (sync .venv to poetry.lock) ──"
	poetry config virtualenvs.in-project true
	poetry install --with dev,ci
	@echo ""
	@echo "── Stage 1: sanity ──"
	find seanergys_modelzoo ci tests -name "*.py" -print0 | xargs -0 $(PYTHON) -m py_compile && echo "✓ syntax OK"
	test -f pyproject.toml && test -d seanergys_modelzoo && test -d ci && test -d tests && echo "✓ structure OK"
	-@chmod +x ci/check_secrets.sh 2>/dev/null || true
	-./ci/check_secrets.sh .
	@echo ""
	@echo "── Stage 2: validate ──"
	$(PYTHON) ci/validate_yaml.py && echo "✓ YAML OK"
	@echo ""
	@echo "── Stage 3: lint (allow_failure) ──"
	-$(PYTHON) -m ruff check seanergys_modelzoo ci tests
	-$(PYTHON) -m ruff format --check seanergys_modelzoo ci tests
	-$(PYTHON) -m mypy seanergys_modelzoo ci tests --ignore-missing-imports --explicit-package-bases
	@echo ""
	@echo "── Stage 4: test (each layer once; combined coverage) ──"
	mkdir -p coverage
	rm -f coverage/.coverage
	COVERAGE_FILE=coverage/.coverage $(PYTEST) tests/unit/ -v \
	    --cov=seanergys_modelzoo --cov-append --cov-report=
	COVERAGE_FILE=coverage/.coverage $(PYTEST) tests/smoke/test_smoke_models.py -v \
	    --cov=seanergys_modelzoo --cov-append --cov-report=
	CI_SKIP_ZENODO=1 COVERAGE_FILE=coverage/.coverage $(PYTEST) tests/smoke/test_smoke_data.py -v -m "not zenodo" \
	    --cov=seanergys_modelzoo --cov-append --cov-report=
	@echo "  (integration needs fixtures — run 'make sample-data' if this fails)"
	CI_SKIP_ZENODO=1 COVERAGE_FILE=coverage/.coverage $(PYTEST) tests/integration/ -v -m "not zenodo" \
	    --cov=seanergys_modelzoo --cov-append --cov-report=
	@echo ""
	@echo "── Stage 5: coverage (combined report) ──"
	COVERAGE_FILE=coverage/.coverage $(PYTHON) -m coverage xml -o coverage/cobertura-coverage.xml
	COVERAGE_FILE=coverage/.coverage $(PYTHON) -m coverage report
	@echo ""
	@echo "── Stage 6: docs (capability tables current?) ──"
	$(PYTHON) ci/gen_capabilities_doc.py --check
	@echo ""
	@echo "── Stage 4b: audit (allow_failure) ──"
	-$(MAKE) audit
	@echo ""
	@echo "── Stage 7 + 8: build wheel + test wheel ──"
	$(MAKE) test-wheel
	@echo ""
	@echo "✓ CI simulation complete — safe to push"

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
