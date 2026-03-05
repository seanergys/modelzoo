# seanergys-modelzoo Makefile
# Run `make help` for usage

.PHONY: help install sample-data test test-unit test-smoke test-datasets lint clean

# Use venv Python (create with: python -m venv .venv)
VENV ?= .venv
PYTHON ?= $(VENV)/bin/python
PYTEST ?= $(VENV)/bin/pytest
export PYTHONPATH := $(shell pwd):$(PYTHONPATH)

# -----------------------------------------------------------------------------
# Help
# -----------------------------------------------------------------------------
help:
	@echo "seanergys-modelzoo Makefile"
	@echo ""
	@echo "Targets:"
	@echo "  make sample-data    Create small datasets for local/CI tests (from Zenodo)"
	@echo "  make test           Run all tests (unit + smoke)"
	@echo "  make test-unit      Run unit tests only"
	@echo "  make test-smoke     Run smoke tests only"
	@echo "  make test-datasets      Run dataset load tests (needs sample-data or network)"
	@echo "  make test-integration   Run integration tests (requires sample-data)"
	@echo "  make lint           Run ruff lint"
	@echo "  make install        Install package in editable mode"
	@echo "  make clean          Remove caches and generated files"
	@echo ""
	@echo "Sample data:"
	@echo "  SAMPLE_MAX_ROWS=50 make sample-data   Limit rows per fixture (default: 100)"
	@echo "  make sample-data -- --fdata-only      Create only F-DATA sample"
	@echo "  make sample-data -- --pm100-only      Create only PM100 sample"
	@echo ""
	@echo "Tests:"
	@echo "  CI_SKIP_ZENODO=1 make test-datasets    Skip Zenodo tests (local fixtures only)"
	@echo "  CI_MAX_SAMPLES=50 make sample-data    Alias for SAMPLE_MAX_ROWS"

# -----------------------------------------------------------------------------
# Install
# -----------------------------------------------------------------------------
install:
	$(PYTHON) -m pip install -e .
	$(PYTHON) -m pip install -r requirements-test.txt

# -----------------------------------------------------------------------------
# Sample data (for local dev and CI)
# -----------------------------------------------------------------------------
sample-data:
	@echo "Creating sample datasets for tests..."
	$(PYTHON) -m pip install -q pandas pyarrow 2>/dev/null || true
	$(PYTHON) scripts/create_sample_data.py $(ARGS)
	@echo "Sample data created in tests/fixtures/sample_data/"
	@echo "  Use: make sample-data ARGS='--fdata-only' or ARGS='--pm100-only'"

# -----------------------------------------------------------------------------
# Tests
# -----------------------------------------------------------------------------
test: test-unit test-smoke
	@echo "All tests passed"

test-unit:
	$(PYTEST) tests/unit/ -v

test-smoke:
	$(PYTEST) tests/smoke/ -v -m "not zenodo"

test-datasets:
	@echo "Running dataset load tests..."
	@echo "  (Use 'make sample-data' first for local fixtures, or tests will use Zenodo)"
	$(PYTEST) tests/smoke/test_datasets_load.py -v

test-integration:
	@echo "Running integration tests (requires sample-data)..."
	@echo "  Run 'make sample-data' first if tests/fixtures/sample_data/ is empty"
	$(PYTEST) tests/integration/ -v

test-all:
	$(PYTEST) tests/ -v

# Full smoke including Zenodo (requires network)
test-smoke-zenodo:
	$(PYTEST) tests/smoke/ -v

# -----------------------------------------------------------------------------
# Lint
# -----------------------------------------------------------------------------
lint:
	$(PYTHON) -m pip install -q ruff 2>/dev/null || true
	ruff check seanergys_modelzoo ci tests --ignore E501

# -----------------------------------------------------------------------------
# Clean
# -----------------------------------------------------------------------------
clean:
	rm -rf .pytest_cache .ruff_cache build/ dist/ *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@echo "Cleaned caches and build artifacts"
