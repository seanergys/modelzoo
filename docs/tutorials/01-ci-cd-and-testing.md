# Tutorial 1: CI/CD and testing in the Model Zoo

## 1. What CI/CD means

**CI** means Continuous Integration. When somebody pushes code or opens a merge request,
GitLab automatically checks the change. The purpose is to find problems before the change
is merged.

**CD** means Continuous Delivery or Continuous Deployment. It normally includes packaging
or releasing software after CI succeeds. In this repository, the pipeline builds and tests
the Python wheel. It does not automatically publish the wheel to a package registry.

The pipeline definition is at the repository root:

```text
.gitlab-ci.yml
```

GitLab reads this file and creates the pipeline jobs.

## 2. Important words

| Word | Simple meaning |
|---|---|
| Pipeline | The complete set of automatic checks for one change. |
| Stage | A group of related jobs, such as `test` or `build`. |
| Job | One command or group of commands run by GitLab. |
| Gate | A check that must pass. If it fails, the pipeline fails. |
| Warn-only job | A useful check whose failure is visible but does not fail the pipeline. |
| Artifact | A file kept by GitLab after a job, such as coverage XML or a wheel. |
| Merge request (MR) | A request to review and merge a branch. |
| Default branch | The main shared branch after a merge. |

In `.gitlab-ci.yml`, gate status is controlled by `allow_failure`:

```yaml
allow_failure: false  # hard gate: failure blocks the pipeline
allow_failure: true   # warning: failure is visible but does not block
```

This value is also the source used by the automatic documentation. There is no second,
manually maintained list of gate statuses.

## 3. What happens after a push

The stages run in this order:

```text
change pushed
    |
    v
sanity -> validate -> lint -> test -> coverage -> docs -> build -> test-wheel
    |
    v
pipeline result: passed, passed with warnings, or failed
```

GitLab can run independent jobs in the same stage at the same time. A later stage normally
starts after the required jobs in earlier stages have completed.

The workflow rules near the top of `.gitlab-ci.yml` avoid duplicate pipelines. If a branch
has an open merge request, the merge-request pipeline is used. On the default branch, the
correctness checks always run. On other branches, `rules:changes` starts only the jobs whose
inputs may have changed.

## 4. Pipeline stages and jobs

The following is a beginner-friendly description. For the always-current table, see
[`../ci-cd.md`](../ci-cd.md).

### Stage 1: `sanity`

These are cheap checks that run on every pipeline.

| Job | What it checks | Current result on failure |
|---|---|---|
| `sanity:python-syntax` | Compiles Python files to find syntax errors. | Blocks |
| `sanity:check-structure` | Confirms important files and directories exist. | Blocks |
| `sanity:check-secrets` | Runs `ci/check_secrets.sh` to detect possible committed secrets. | Blocks |

### Stage 2: `validate`

| Job | What it checks | Current result on failure |
|---|---|---|
| `validate:yaml-json` | Uses `ci/validate_yaml.py` to parse YAML and JSON files. | Blocks |

This catches an invalid `.gitlab-ci.yml` or policy file early.

### Stage 3: `lint`

| Job | Tool | What it checks | Current result on failure |
|---|---|---|---|
| `lint:python` | Ruff | Common Python mistakes and style rules. | Warns |
| `lint:format` | Ruff | Whether files follow the required format. | Warns |
| `lint:mypy` | mypy | Type consistency. | Warns |

These jobs currently give quality warnings. They do not replace the hard correctness tests.

### Stage 4: `test`

| Job | Location or tool | What it checks | Current result on failure |
|---|---|---|---|
| `test:unit` | `tests/unit/` | Small components in isolation. | Blocks |
| `test:smoke-models` | `tests/smoke/test_smoke_models.py` | Model discovery, construction, and training configuration. | Blocks |
| `test:smoke-data` | `tests/smoke/test_smoke_data.py` | Dataset discovery, contracts, and local fixture loading. | Blocks |
| `test:integration` | `tests/integration/` | Full offline model and dataset lifecycle. | Blocks |
| `test:zenodo` | Zenodo-marked integration tests | Real small downloads and a real lifecycle. | Warns |
| `test:audit` | `pip-audit` | Known vulnerabilities in dependencies. | Warns |

The offline tests use files under `tests/fixtures/sample_data/`. Only `test:zenodo` should
contact Zenodo. This separation keeps the main correctness tests stable when an external
service is unavailable.

### Stage 5: `coverage`

Each main test job writes a separate coverage data file. `coverage:report` combines the
available files and creates:

```text
coverage/cobertura-coverage.xml
```

GitLab stores it as a coverage artifact. The job uses optional dependencies, so it can
combine the results that exist even when a test job was correctly skipped by its change
rules.

### Stage 6: `docs`

| Job | Where it runs | What it does | Current result on failure |
|---|---|---|---|
| `docs:check` | Branches and merge requests | Reports if `docs/ci-cd.md` is stale. | Warns |
| `docs:autogen` | Default branch | Regenerates and commits changed tables. | Warns |

These jobs are explained fully in
[Tutorial 2](02-automatic-documentation.md).

### Stage 7: `build`

`build:wheel` runs `poetry build --format wheel`. The resulting `.whl` file is kept in
`dist/` as an artifact. A package that cannot be built is not ready to deliver, so this job
blocks.

### Stage 8: `test-wheel`

`test:wheel` installs the built wheel and runs `ci/verify_wheel.py`. It clears `PYTHONPATH`
so Python imports the installed wheel, not the source directory by accident. The verifier
walks the package modules dynamically. This job blocks because consumers need a package
that installs and imports correctly.

## 5. The three test levels

### Unit tests: one component at a time

Location:

```text
tests/unit/
```

They check configurators, dataloaders, dataset parsing, metadata, logger behaviour, model
base classes, concrete models, saving and loading, and error cases. They should be fast and
should normally avoid network access.

### Smoke tests: can the main objects be found and created?

Locations:

```text
tests/smoke/test_smoke_models.py
tests/smoke/test_smoke_data.py
```

Important model smoke functions include:

- `test_model_discovery()` — at least one model was found.
- `test_model_instantiation()` — every discovered model can be constructed.
- `test_model_get_train_config()` — the training configuration has the expected shape.

Important dataset smoke functions include:

- `test_dataset_discovery()` — dataset classes were found.
- `test_dataset_contract_via_model_config()` — a dataset follows the common interface.
- `test_dataset_fixture_has_data()` — committed test data is present and usable.
- the `is_dummy` and Zenodo tests — small real-data loading works where supported.

### Integration tests: does the complete workflow work?

Main file:

```text
tests/integration/test_model_pipeline.py
```

`test_get_train_config_structure()` checks the structural contract without loading data.

`test_full_pipeline_offline()` then checks this lifecycle for every discovered pair:

```text
get config
  -> load fixture
  -> check dataset
  -> create dataloader
  -> train
  -> predict
  -> save
  -> reload
  -> predict again
  -> compare predictions
  -> check metadata
```

`test_full_pipeline_zenodo()` checks a smaller version using a real `is_dummy=True` Zenodo
download. It is selected with the `zenodo` pytest marker.

## 6. How models and datasets enter CI automatically

The central discovery file is:

```text
tests/conftest.py
```

Its important items are:

| Name | Meaning |
|---|---|
| `_collect_model_classes()` | Scans `seanergys_modelzoo/models/tasks/` for concrete model subclasses. |
| `_collect_dataset_classes()` | Scans `seanergys_modelzoo/datasets/` for concrete dataset subclasses. |
| `MODEL_CLASSES` | All discovered model classes. |
| `DATASET_CLASSES` | All discovered dataset classes. |
| `_collect_model_dataset_pairs()` | Reads each model's `supported_datasets`. |
| `MODEL_DATASET_PAIRS` | Every `(model class, dataset ID)` combination to test. |

The smoke and integration tests use these collections as pytest parameters. Therefore,
contributors do not maintain a separate hardcoded list in the pipeline.

For a new model to participate correctly:

1. Put its module below `seanergys_modelzoo/models/tasks/`.
2. Subclass the appropriate common model class.
3. Set `supported_datasets`.
4. Implement `get_train_config(dataset_id)`.
5. Make the returned dataset parameters work with small local fixtures and, where relevant,
   `is_dummy=True`.
6. Run the local checks and regenerate the CI documentation.

## 7. Currently discovered support

The current model–dataset combinations are:

| Model | Dataset | Dataset ID | CI state |
|---|---|---|---|
| JPCP | PM100Dataset | `pm100` | Tested; must pass |
| JPCP | FDataDataset | `f-data` | Tested; must pass |
| MACK | FDataDataset | `f-data` | Tested; must pass |
| MCBound | FDataDataset | `f-data` | Tested; must pass |

The discovered datasets also include `M100Dataset` and `SCRIPTAIDataset`, but they are not
currently connected to a model through a non-empty `DATASET_ID` pair. Unit tests still
cover these dataset classes.

The live capability table in [`../ci-cd.md`](../ci-cd.md) is authoritative. This tutorial
is a teaching snapshot and may change less often.

### What `xfail(strict)` means

A known-broken pair can be listed under `integration_xfail` in `ci/policy.yml`. **The list is
empty today** — every pair must pass — but when an entry exists pytest still runs that
integration case:

- If it fails as expected, the result is `XFAIL` and the pipeline can continue.
- If it unexpectedly passes, strict mode reports `XPASS` as a failure. This tells the team
  to remove the obsolete exception.

This is safer than silently skipping the test.

## 8. Files colleagues should know

| Location | Purpose |
|---|---|
| `.gitlab-ci.yml` | Pipeline stages, jobs, commands, trigger rules, and hard/warn status. |
| `pyproject.toml` | Python dependencies and tool configuration. |
| `poetry.lock` | Exact resolved dependency versions. |
| `Makefile` | Short local commands that mirror common CI actions. |
| `tests/conftest.py` | Automatic model and dataset discovery. |
| `tests/unit/` | Component tests. |
| `tests/smoke/` | Discovery and construction tests. |
| `tests/integration/` | Full lifecycle tests. |
| `tests/fixtures/` | Small committed data used by offline tests. |
| `ci/policy.yml` | Human explanations, expected failures, audit exceptions, and skip notes. |
| `ci/gen_capabilities_doc.py` | Automatic CI documentation generator. |
| `ci/validate_yaml.py` | YAML and JSON validation. |
| `ci/verify_wheel.py` | Installed-wheel verification. |
| `ci/check_secrets.sh` | Basic secret scan. |
| `docs/ci-cd.md` | Generated current reference plus human-written guidance. |

## 9. Commands to run locally

First-time setup:

```bash
make install-ci
make sample-data
```

During normal development:

```bash
make format          # fix formatting
make pre-push        # fast local gate
make test-all        # unit + smoke + integration
make docs-ci         # regenerate CI tables after relevant changes
make docs-ci-check   # confirm generated tables are current
```

To simulate the complete GitLab pipeline locally:

```bash
make ci
```

Useful focused commands:

```bash
make test-unit
make test-smoke-models
make test-smoke-data
make test-integration
make test-wheel
```

## 10. Normal merge-request checklist

1. Make the code or CI change.
2. Add or update tests.
3. Run `make format` and `make pre-push`.
4. Run `make test-all` for model, dataset, or pipeline behaviour changes.
5. If CI structure, policy, tests, models, or datasets changed, run `make docs-ci`.
6. Review `git diff`, especially the generated `docs/ci-cd.md` table changes.
7. Run `make docs-ci-check`.
8. Commit the implementation, tests, and generated documentation together.
9. Open the merge request and review every blocking failure and warning.

Continue with [Tutorial 2](02-automatic-documentation.md) to understand how the generated
tables and automatic gate status work.
