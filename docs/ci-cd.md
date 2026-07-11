# CI/CD Capabilities & Rules Reference

> **Auto-generated tables — do not edit between the `GENERATED` markers.**
> The tables below are produced by `ci/gen_capabilities_doc.py` from
> `.gitlab-ci.yml` (jobs/rules), the model/dataset code (capability matrix), and
> `ci/policy.yml` (rationale). Regenerate with `make docs-ci`. On the default
> branch the `docs:autogen` job regenerates and commits this file automatically,
> so it never goes stale. Prose outside the markers is preserved.
>
> **See also:** [`TESTING_AND_CI_GUIDE.md`](TESTING_AND_CI_GUIDE.md) (how to run
> tests locally), [`TESTING_AND_CI_PLAN.md`](TESTING_AND_CI_PLAN.md) (roadmap),
> [`DATASET_ID_AND_SUPPORTED_DATASETS.md`](DATASET_ID_AND_SUPPORTED_DATASETS.md)
> (the model/dataset contract).

## Purpose

This document is the single reference for **what the CI/CD pipeline tests, and
under which rules**, so it can be shared with colleagues. To request a change to
any rule, gate, or capability, open an issue with the **CI Change Request**
template (`.gitlab/issue_templates/CI_Change_Request.md`).

## Pipeline stages

<!-- BEGIN:GENERATED pipeline-stages -->
**Stage order:** `sanity` → `validate` → `lint` → `test` → `coverage` → `docs` → `build` → `test-wheel`
<!-- END:GENERATED pipeline-stages -->

## Jobs, triggers, and gates

Every job, the condition under which it runs, and whether a failure blocks the
pipeline or only warns.

<!-- BEGIN:GENERATED jobs -->
| Stage | Job | Trigger | On failure | Runs |
| --- | --- | --- | --- | --- |
| sanity | `sanity:check-secrets` | `always` | Warns | ./ci/check_secrets.sh . |
| sanity | `sanity:check-structure` | `always` | Blocks | test -f pyproject.toml |
| sanity | `sanity:python-syntax` | `always` | Blocks | find seanergys_modelzoo ci tests scripts -name "*.py" -print0 \| xargs -0 -r python -m py… |
| validate | `validate:yaml-json` | `always` | Blocks | python ci/validate_yaml.py |
| lint | `lint:format` | `rules_code` | Warns | ruff format --check seanergys_modelzoo ci tests |
| lint | `lint:mypy` | `rules_code` | Warns | mypy seanergys_modelzoo ci tests --ignore-missing-imports --explicit-package-bases |
| lint | `lint:python` | `rules_code` | Warns | ruff check seanergys_modelzoo ci tests |
| test | `test:audit` | `rules_deps` | Warns | poetry export -f requirements.txt --without-hashes --with dev,ci -o /tmp/poetry-audit-req… |
| test | `test:integration` | `rules_integration` | Blocks | CI_SKIP_ZENODO=1 poetry run pytest tests/integration/ -v -m "not zenodo" --cov=seanergys_… |
| test | `test:smoke-data` | `rules_smoke` | Blocks | poetry run pytest tests/smoke/test_smoke_data.py -v -m "not zenodo" --cov=seanergys_model… |
| test | `test:smoke-models` | `rules_smoke` | Blocks | poetry run pytest tests/smoke/test_smoke_models.py -v --cov=seanergys_modelzoo --cov-repo… |
| test | `test:unit` | `rules_unit` | Blocks | poetry run pytest tests/unit/ -v --tb=short --cov=seanergys_modelzoo --cov-report= |
| test | `test:zenodo` | `rules_zenodo` | Warns | poetry run pytest tests/integration/ -v -m zenodo |
| coverage | `coverage:report` | `rules_code` | Blocks | if ls coverage-data/.coverage.* >/dev/null 2>&1; then coverage combine coverage-data cove… |
| docs | `docs:autogen` | `default-branch` | Warns | poetry run python ci/gen_capabilities_doc.py |
| docs | `docs:check` | `merge-request` | Warns | poetry run python ci/gen_capabilities_doc.py --check |
| build | `build:wheel` | `rules_wheel` | Blocks | poetry build --format wheel |
| test-wheel | `test:wheel` | `rules_wheel` | Blocks | python ci/verify_wheel.py |
<!-- END:GENERATED jobs -->

### Trigger legend

<!-- BEGIN:GENERATED triggers -->
| Trigger | When the job runs |
| --- | --- |
| `always` | Runs on every pipeline (cheap checks < 10s, no change filter). |
| `default-branch` | Runs only on the default branch (post-merge). |
| `merge-request` | Runs on branches / merge requests (excluded on the default branch). |
| `rules_code` | Any source, test, script, CI, or dependency change. |
| `rules_deps` | Only pyproject.toml / poetry.lock / .gitlab-ci.yml changed. |
| `rules_integration` | Source, tests/integration/**, conftest, create_sample_data.py, or deps. |
| `rules_smoke` | Source, tests/smoke/**, conftest, or dependency change. |
| `rules_unit` | Source, tests/unit/**, conftest, or dependency change. |
| `rules_wheel` | Source or pyproject.toml changed (packaging-relevant). |
| `rules_zenodo` | Default branch, or a change under seanergys_modelzoo/datasets/**, tests/integration/**, or conftest. |
<!-- END:GENERATED triggers -->

## Pass / fail engineering decisions

Why each job blocks the pipeline or is allowed to fail. The *what* (above) is
auto-derived from `.gitlab-ci.yml`; the *why* below is maintained in
`ci/policy.yml`.

<!-- BEGIN:GENERATED rationale -->
| Job | On failure | Why |
| --- | --- | --- |
| `sanity:check-secrets` | Warns | Warn-only: the regex scan can false-positive; a human triages hits. |
| `sanity:check-structure` | Blocks | Guards the repo layout that every later job and import assumes. |
| `sanity:python-syntax` | Blocks | Broken syntax must never enter the pipeline; a cheap hard gate. |
| `validate:yaml-json` | Blocks | Invalid YAML/JSON (incl. this pipeline) would break CI itself — hard gate. |
| `lint:format` | Warns | Formatting drift shouldn't block merges; run `make format` to fix. |
| `lint:mypy` | Warns | Type coverage is incomplete; surfaced as a warning, not a gate. |
| `lint:python` | Warns | Style/lint issues are quality signals, not correctness; non-blocking. |
| `test:audit` | Warns | Dependency CVEs are informational and often unfixable immediately; warn-only. |
| `test:integration` | Blocks | End-to-end model×dataset pipeline must pass; the core correctness gate. |
| `test:smoke-data` | Blocks | Dataset contract + fixtures must load; hard gate (runs without Zenodo). |
| `test:smoke-models` | Blocks | Model discovery/instantiation must hold or nothing downstream works. |
| `test:unit` | Blocks | Component correctness is a hard gate — the fastest signal of breakage. |
| `test:zenodo` | Warns | The only job that reaches Zenodo: downloads a small is_dummy subset (memory-safe columns+filters read, not a whole-file load) and runs train→predict→save/load. Warn-only because Zenodo is an external service — downtime must not block merges; a failure is a visible connectivity/regression signal. Flip allow_failure to false to make it a hard gate. |
| `coverage:report` | Blocks | Combines per-job coverage into one report; fails only on tooling error. |
| `docs:autogen` | Warns | Regenerates + commits docs on the default branch; warn-only so a token or push hiccup never breaks main. |
| `docs:check` | Warns | Warns on merge requests when docs/ci-cd.md is stale; not blocking. |
| `build:wheel` | Blocks | A non-buildable package is a release blocker — hard gate. |
| `test:wheel` | Blocks | The distributed wheel must import cleanly for consumers — hard gate. |
<!-- END:GENERATED rationale -->

## Model × dataset capability matrix

Which models are tested against which datasets. Discovered automatically from each
model's `supported_datasets` and the auto-discovery in `tests/conftest.py` — adding
a model or dataset updates this table on the next regeneration.

<!-- BEGIN:GENERATED capabilities -->
| Model | Task | Supported dataset | DATASET_ID | Tested in CI |
| --- | --- | --- | --- | --- |
| JPCP | Regression | PM100Dataset | `pm100` | yes |
| JPCP | Regression | FDataDataset | `f-data` | yes |
| MACK | Classification | FDataDataset | `f-data` | xfail |
| MCBound | Classification | FDataDataset | `f-data` | xfail |
<!-- END:GENERATED capabilities -->

## Datasets

<!-- BEGIN:GENERATED datasets -->
| Dataset | DATASET_ID | is_dummy mode |
| --- | --- | --- |
| FDataDataset | `f-data` | yes |
| M100Dataset | `—` | yes |
| PM100Dataset | `pm100` | yes |
| SCRIPTAIDataset | `—` | yes |
<!-- END:GENERATED datasets -->

## Test inventory

Every test file grouped by layer, with the check it performs (from its docstring).

<!-- BEGIN:GENERATED test-inventory -->
| Layer | File | Checks |
| --- | --- | --- |
| unit | `test_configurator.py` | Unit tests for Seanergys configurator (Pydantic params). |
| unit | `test_coverage_extra.py` | Additional unit tests targeting branches not reachable through the happy |
| unit | `test_dataloader.py` | Unit tests for SeanergysDataloader (type guard + from_config). |
| unit | `test_dataloader_params.py` | Unit tests for SeanergysDataloaderParams validation. |
| unit | `test_dataset_contract.py` | Unit tests for dataset contract (__len__, __getitem__, supported_features). |
| unit | `test_dataset_parsers.py` | Unit tests for dataset file/node-spec parsing logic. |
| unit | `test_logger.py` | Unit tests for SeanergysLogger. |
| unit | `test_m100.py` | Unit tests for M100Dataset. |
| unit | `test_metadata.py` | Unit tests for SeanergysModelMetadata. |
| unit | `test_model_subclasses.py` | Unit tests for the concrete model subclasses (MACK, MCBound, JPCP). |
| unit | `test_parquet_datasets.py` | Unit tests for concrete parquet datasets (PM100, F-DATA) using tiny local |
| unit | `test_script_ai.py` | Unit tests for SCRIPTAIDataset using a local features.csv + script files. |
| unit | `test_sklearn_model.py` | Unit tests for SeanergysSklearnModel. |
| unit | `test_utils.py` | Unit tests for ci.utils (discovery helpers). |
| smoke | `test_smoke_data.py` | Smoke tests: dataset discovery, contract validation, and data loading. |
| smoke | `test_smoke_models.py` | Smoke tests: model discovery, instantiation, and train-config structure. |
| integration | `test_model_pipeline.py` | Integration tests: the full pipeline for every (model, dataset) pair. |
<!-- END:GENERATED test-inventory -->
