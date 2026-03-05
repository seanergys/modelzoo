# GitLab CI/CD Pipeline

The pipeline runs automatically on every push and merge request using GitLab shared runners.

## Stages

| Stage    | Jobs                | Description                                       |
|----------|---------------------|---------------------------------------------------|
| **sanity**   | python-syntax, check-structure | Python syntax check and repo structure validation |
| **validate** | yaml-json           | Validates all `.yml`, `.yaml`, `.json` files       |
| **lint**     | python              | Ruff linting on Python files                      |
| **test**     | unit, smoke, import-check, validate-models, validate-datasets | Pytest unit/smoke + import + model/dataset validation |

## Job Details

- **sanity:python-syntax** — Compiles Python files in `seanergys_modelzoo/`, `ci/`, `tests/`.
- **sanity:check-structure** — Ensures `setup.py`, `seanergys_modelzoo/`, `ci/`, `tests/` exist.
- **test:unit** — Runs `pytest tests/unit/` (unit tests).
- **test:smoke** — Runs `pytest tests/smoke/` (smoke tests).
- **validate:yaml-json** — Uses `ci/validate_yaml.py` to validate config files.
- **lint:python** — Runs ruff when `.py` files change.
- **test:import-check** — Verifies core package imports work.
- **test:validate-models** — Runs `pytest tests/smoke/test_models_smoke.py` + `ci/validate_models.py`; automatic. Requires `ci/requirements-ci.txt`, Zenodo for full validation.
- **test:validate-datasets** — Runs `pytest tests/smoke/test_datasets_smoke.py` + `ci/validate_datasets.py`; automatic.

## Directory Layout

All CI and validation tooling lives in `ci/`:

```
ci/
├── validate_yaml.py      # YAML/JSON validation
├── validate_models.py    # Model discovery & validation
├── validate_datasets.py  # Dataset discovery & validation
├── utils.py              # Shared discovery helpers
└── requirements-ci.txt   # Dependencies for model validation
```

## Caching

Pip packages are cached per branch (`$CI_COMMIT_REF_SLUG`).

## Running Locally

```bash
export PYTHONPATH="${PWD}:${PYTHONPATH}"

# Install and run tests (via Makefile)
make install
make sample-data          # Create small datasets for tests (from Zenodo)
make test                 # Unit + smoke tests
make test-datasets        # Dataset load tests (use sample-data first)

# Or manually:
pip install -r requirements-test.txt
pytest tests/unit/ tests/smoke/ -v -m "not zenodo"

# Validate YAML/JSON
pip install pyyaml && python ci/validate_yaml.py

# Model validation (requires deps and Zenodo access)
pip install -r ci/requirements-ci.txt
python ci/validate_models.py --model-folder seanergys_modelzoo/models

# Dataset validation (discovery only)
pip install pydantic torch pyarrow
python ci/validate_datasets.py --data-folder seanergys_modelzoo/datasets
```

### Sample data for tests

Run `make sample-data` to create small parquet files in `tests/fixtures/sample_data/` from Zenodo. This enables dataset load tests without network during test runs. See `tests/fixtures/README.md` and `make help`.
