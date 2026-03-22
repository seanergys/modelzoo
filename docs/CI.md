# GitLab CI/CD Pipeline

The pipeline runs on every push and merge request using GitLab shared runners.

## Stages

| Stage    | Jobs              | Description                                      |
|----------|-------------------|--------------------------------------------------|
| **sanity**   | python-syntax, check-structure | Python syntax check and repo structure validation |
| **validate** | yaml-json         | Validates all `.yml`, `.yaml`, `.json` files     |
| **lint**     | python            | Linting (ruff/pyflakes if available, optional)  |
| **test**     | import-check, validate-models | Import verification and model validation   |

## Job Details

- **sanity:python-syntax** — Compiles Python files to verify syntax.
- **sanity:check-structure** — Ensures `setup.py`, `seanergys_modelzoo/`, `scripts/` exist.
- **validate:yaml-json** — Uses `ci/validate_yaml.py` to validate config files.
- **lint:python** — Runs only when `.py` files change; fails gracefully if no linter is installed.
- **test:import-check** — Verifies core package imports work (lightweight).
- **test:validate-models** — Runs `scripts/validate_models.py`; requires `ci/requirements-ci.txt` and network (Zenodo) for full model validation. Triggers on model/script changes or can be run manually.

## Caching

Pip packages are cached per branch (`$CI_COMMIT_REF_SLUG`) to speed up test jobs.

## Helper Scripts

- `ci/validate_yaml.py` — Validates YAML and JSON files.
- `ci/requirements-ci.txt` — Dependencies for the `test:validate-models` job.

## Running Locally

```bash
# Validate YAML/JSON
pip install pyyaml && python ci/validate_yaml.py

# Run model validation (requires deps and Zenodo access)
pip install -r ci/requirements-ci.txt
export PYTHONPATH="${PWD}:${PYTHONPATH}"
python scripts/validate_models.py --model-folder seanergys_modelzoo/models
```
