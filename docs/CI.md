# GitLab CI/CD Pipeline

The pipeline runs automatically on every push and merge request using GitLab shared runners.

## Stages

| Stage    | Jobs                | Description                                       |
|----------|---------------------|---------------------------------------------------|
| **sanity**   | python-syntax, check-structure, check-secrets | Python syntax, repo structure, secret scan |
| **validate** | yaml-json           | Validates all `.yml`, `.yaml`, `.json` files       |
| **lint**     | python, format, mypy | Ruff lint, format, and optional mypy on Python files |
| **test**     | unit, smoke, import-check, validate-models, validate-datasets, integration, audit | Pytest + validation + integration + dependency audit |

## Job Details

### Sanity (always runs)

| Job | Description | Allow failure |
|-----|-------------|--------------|
| **sanity:python-syntax** | Compiles Python files in `seanergys_modelzoo/`, `ci/`, `tests/` | No |
| **sanity:check-structure** | Ensures `pyproject.toml`, `seanergys_modelzoo/`, `ci/`, `tests/` exist | No |
| **sanity:check-secrets** | Scans for hardcoded secrets (api_key, etc.) in code | Yes |

### Validate

| Job | Trigger | Description | Allow failure |
|-----|---------|-------------|--------------|
| **validate:yaml-json** | On config change / always | Uses `ci/validate_yaml.py` to validate YAML/JSON files | No |

### Lint

| Job | Trigger | Description | Allow failure |
|-----|---------|-------------|--------------|
| **lint:python** | On `.py` changes | `ruff check seanergys_modelzoo ci tests` | Yes |
| **lint:format** | On `.py` changes | `ruff format --check seanergys_modelzoo ci tests` | Yes |
| **lint:mypy** | On `.py` changes | Type checking with mypy | Yes |

### Test

| Job | Trigger | Description | Allow failure |
|-----|---------|-------------|--------------|
| **test:unit** | On `.py` changes | `pytest tests/unit/` | No |
| **test:smoke** | On `.py` changes | `pytest tests/smoke/` | No |
| **test:import-check** | Always | Verifies core package imports | No |
| **test:validate-models** | On models/ci change / always | `pytest tests/smoke/test_models_smoke.py` + `ci/validate_models.py` | Yes |
| **test:validate-datasets** | On datasets/ci change / always | `pytest tests/smoke/test_datasets_smoke.py` + `ci/validate_datasets.py` | Yes |
| **test:integration** | On models/datasets/tests/scripts change | `make sample-data` then `pytest tests/integration/` | No |
| **test:audit** | On `pyproject.toml`/`poetry.lock` changes | `poetry export` → `pip-audit` | Yes |

## Directory Layout

All CI and validation tooling lives in `ci/`:

```
ci/
├── validate_yaml.py      # YAML/JSON validation
├── validate_models.py    # Model discovery & validation
├── validate_datasets.py  # Dataset discovery & validation
└── utils.py             # Shared discovery helpers
```

Dependencies are managed in `pyproject.toml` (Poetry) via the `ci` dependency group.

## Caching

Pip packages are cached per branch (`$CI_COMMIT_REF_SLUG`).

## Running Locally

```bash
export PYTHONPATH="${PWD}:${PYTHONPATH}"

# Install and run tests (via Makefile)
make install              # poetry install --with dev
make sample-data          # Create small datasets for tests (from Zenodo)
make test                 # Unit + smoke tests
make test-datasets        # Dataset load tests (use sample-data first)
make test-integration     # Integration tests (use sample-data first)
make lint                # Ruff lint
make format              # Ruff format
make typecheck           # Mypy (optional)
make audit               # pip-audit for dependency vulnerabilities
make check-secrets       # Scan for accidental secrets in code

# Or manually (Poetry):
poetry install --with dev
poetry run pytest tests/unit/ tests/smoke/ -v -m "not zenodo"

# Validate YAML/JSON
pip install pyyaml && python ci/validate_yaml.py

# Model validation (requires ci deps)
poetry install --with dev,ci
poetry run python ci/validate_models.py --model-folder seanergys_modelzoo/models

# Dataset validation (discovery only)
poetry run python ci/validate_datasets.py --data-folder seanergys_modelzoo/datasets
```

### Sample data for tests

Run `make sample-data` to create small parquet files in `tests/fixtures/sample_data/` from Zenodo. This enables dataset load tests without network during test runs. See `tests/fixtures/README.md` and `make help`.
