# Testing & CI Guide
_seanergys-modelzoo | Author: Mohsen | Updated: 2026-03-22_

This guide explains how to run tests locally, what each test checks, and what happens
in each stage of the GitLab CI pipeline.

---

## Quick Start (local)

```bash
# 1. Install dependencies
make install-ci

# 2. Create small fixture files (needed for dataset + integration tests)
make sample-data

# 3. Run fast tests before every push
make test

# 4. Run everything (mirrors CI)
make ci
```

---

## Tools Used in CI and Testing

| Tool | Role | What it does | Example |
|---|---|---|---|
| **pytest** | Test runner | Discovers and runs all tests in `tests/`. Supports markers, parametrize, and fixtures. | `pytest tests/unit/ -v` |
| **Poetry** | Dependency manager | Manages packages and dependency groups (`dev`, `ci`). Used by CI to install exact versions. | `poetry install --with dev,ci` |
| **ruff check** | Linter | Checks for unused imports, undefined names, bad patterns, and code style violations. | `ruff check seanergys_modelzoo ci tests` |
| **ruff format** | Formatter | Checks (or fixes) code formatting. Replaces Black as the formatter. | `ruff format --check seanergys_modelzoo` |
| **mypy** | Type checker | Checks type annotations statically. Run with `--ignore-missing-imports` since heavy ML deps are not installed in the lint job. | `mypy seanergys_modelzoo --ignore-missing-imports` |
| **pip-audit** | Security scanner | Scans all dependencies for known CVEs using the PyPI advisory database. | `pip-audit -r requirements.txt` |
| **pyyaml** | YAML parser | Used by `ci/validate_yaml.py` to parse and validate all `.yml`/`.yaml` files. | `yaml.safe_load(open(".gitlab-ci.yml"))` |
| **py_compile** | Syntax checker | Compiles every `.py` file to catch syntax errors before any test runs. Built into Python. | `python -m py_compile myfile.py` |
| **black** | Formatter (dev) | Auto-formats Python code. Available locally via `make format`. CI uses ruff format instead. | `black seanergys_modelzoo` |
| **pydantic** | Data validation | Used by config classes (`SeanergysDatasetParams`, `SeanergysDataloaderParams`, etc.) to validate types and fields at runtime. | `SeanergysDatasetParams(input_features=["x"])` |

### Where each tool is installed

| Tool | Installed in group | Installed with |
|---|---|---|
| pytest, ruff, black, pydantic | `dev` | `poetry install --with dev` |
| numpy, pandas, torch, sklearn, xgboost, sentence-transformers, pyarrow | `ci` | `poetry install --with ci` |
| pyyaml | inline in CI job | `pip install pyyaml` |
| mypy, types-PyYAML | inline in CI job | `pip install mypy types-PyYAML` |
| pip-audit | inline in CI job | `pip install pip-audit` |

---

## Running Tests Locally

Yes — you should always run tests locally before pushing. It saves time and avoids
failed pipelines.

### Prerequisites

```bash
# Install Poetry if not already installed
pip install poetry

# Install all dependencies (ML libs included)
make install-ci

# Create fixture data files (downloads ~MB from Zenodo once)
make sample-data
```

### Available test commands

| Command | What it runs | When to use |
|---|---|---|
| `make test` | Unit + smoke (no network) | Before every push — fast |
| `make test-unit` | `tests/unit/` only | When changing base classes or utils |
| `make test-smoke` | `tests/smoke/` — no network (Approach A contract checks + model discovery) | Before every push — fast |
| `make test-smoke-full` | `tests/smoke/` — includes Approach B (needs Zenodo network) | When changing dataset loading code |
| `make test-datasets` | Dataset load tests | When changing dataset code |
| `make test-pipeline` | Full model pipeline (train→predict→save→load) | When changing model code |
| `make test-integration` | All `tests/integration/` | Before opening a MR |
| `make test-all` | Everything | Final check before MR |
| `make ci` | Mirrors full GitLab pipeline | To simulate CI locally |
| `make clean` | Remove caches and build artifacts | General housekeeping |
| `make clean-fixtures` | Delete `tests/fixtures/sample_data/` | Force fresh fixture download next `make sample-data` |
| `make clean-all` | `clean` + `clean-fixtures` | Full reset |

### Why `make ci` does not include `test-smoke-full`

`make ci` mirrors the GitLab pipeline exactly. In GitLab CI, the smoke stage
runs without network access — no Zenodo downloads are allowed there.

The pipeline handles Approach B (model-based dataset loading) in the **integration
stage**, not the smoke stage: `test:integration` runs `create_sample_data.py` first
(which downloads small fixtures from Zenodo once), then all integration tests run
offline against those local files. So Approach B is already covered in `make ci`
via `test_full_pipeline` — just not in the smoke stage.

| Command | Network | When to use |
|---|---|---|
| `make test-smoke` | No | Before every push — fast, offline |
| `make test-smoke-full` | Yes (Zenodo) | When specifically testing Approach B dataset loading |
| `make ci` | No for smoke, Yes for integration fixtures | Full pipeline simulation |

### Current limitation: integration stage requires network

**If GitLab CI has no internet access, the integration stage will also fail.**

The integration stage currently needs network because:
1. `create_sample_data.py` downloads fixture files from Zenodo
2. Francesco's `is_dummy=True` still downloads from Zenodo with filters — it does
   not generate synthetic data in memory

This means the full pipeline cannot run in a fully offline CI environment today.
The fix requires Francesco to implement `is_dummy=True` properly (see
`docs/COLLEAGUE_FEEDBACK.md §6.3`): generate a small synthetic DataFrame in memory
instead of downloading from Zenodo. Once that is done:
- `create_sample_data.py` becomes unnecessary for CI
- `is_dummy=True` works with zero network access
- Both smoke and integration stages run fully offline

### Skip Zenodo downloads locally

```bash
CI_SKIP_ZENODO=1 make test-smoke    # uses local fixtures only, no network
```

### Run a single test file

```bash
.venv/bin/pytest tests/unit/test_configurator.py -v
.venv/bin/pytest tests/integration/test_model_pipeline.py -v -s
```

### Run a single test by name

```bash
.venv/bin/pytest tests/smoke/test_models_smoke.py::test_model_discovery -v
```

---

## Test Structure

```
tests/
├── conftest.py                      # Shared fixtures + model auto-discovery
├── unit/                            # Fast, isolated, no I/O
│   ├── test_utils.py
│   ├── test_logger.py
│   ├── test_configurator.py
│   ├── test_dataset_contract.py
│   ├── test_metadata.py
│   └── test_dataloader_params.py
├── smoke/                           # Import, discover, instantiate — no training
│   ├── test_models_smoke.py
│   ├── test_datasets_smoke.py
│   └── test_datasets_load.py
├── integration/                     # Full pipeline with real data
│   ├── conftest.py
│   ├── test_model_pipeline.py       ← key: auto-tests every model
│   ├── test_model_train.py
│   └── test_model_save_load.py
└── fixtures/
    └── sample_data/
        └── sample_<datasetname>.parquet   (one per dataset, created by `make sample-data`)
```

---

## What Each Test Checks

### Unit Tests (`tests/unit/`)

Fast, no I/O, no real data. Test individual components in isolation.

| Test file | What it checks |
|---|---|
| `test_utils.py` | `retrieve_instances_from_file` and `import_module_from_file` from `ci/utils.py` |
| `test_logger.py` | `SeanergysLogger` initialises and logs at different levels |
| `test_configurator.py` | Pydantic config classes: `SeanergysModelParams`, `SeanergysDatasetParams`, `SeanergysDataloaderParams` |
| `test_dataset_contract.py` | `SeanergysDataset` base contract: `__len__`, `__getitem__`, `get_stats` using a synthetic dataset |
| `test_metadata.py` | `SeanergysModelMetadata` stores and serialises correctly |
| `test_dataloader_params.py` | `SeanergysDataloaderParams` validates fields correctly |

### Smoke Tests (`tests/smoke/`)

Quick sanity checks — imports, discovery, instantiation. **No training.** The purpose is
to catch broken imports, missing constructors, or broken `get_dummy_params()` before
running the slower integration tests.

#### `test_models_smoke.py`

| Test | What it does |
|---|---|
| `test_logger_imports` | Imports `SeanergysLogger`, checks it is not None |
| `test_ci_utils_imports` | Imports `import_module_from_file` and `retrieve_instances_from_file` from `ci/utils.py` |
| `test_model_discovery` | Scans `models/` folder, asserts at least 1 `SeanergysModel` subclass is found |
| `test_model_instantiation` | Instantiates every discovered model with minimal hyperparams (`n_estimators=2, n_jobs=1`) — no training, just checks the constructor does not crash |

#### `test_datasets_smoke.py`

| Test | What it does |
|---|---|
| `test_dataset_discovery` | Asserts at least 1 `SeanergysDataset` subclass is discoverable |
| `test_dataset_dummy_mode` | For each discovered dataset: calls `get_dummy_params()`, instantiates with `is_dummy=True`, calls `load_data()`, checks `len(dataset) > 0` and `dataset[0]` is not None. Skips with a clear message if `get_dummy_params()` is not implemented. |

#### `test_datasets_load.py`

| Test | What it does |
|---|---|
| `test_dataset_loads_with_dummy` | Loads each dataset with `is_dummy=True` — no network needed. Checks `len >= 1` and `dataset[0]` returns `(x, y)` |
| `test_dataset_loads_from_zenodo` | Loads each dataset from its Zenodo source with `is_dummy=True`. Skipped if `CI_SKIP_ZENODO=1` or if `use_zenodo_url` is not supported. |

**Key point:** smoke tests are the "does it even start?" layer. They do not train any model
or run the full pipeline — that is the job of the integration tests.

### Integration Tests (`tests/integration/`)

Full pipeline with real data from fixture files. Slower — run before opening a MR.

| Test file | What it checks |
|---|---|
| `test_model_pipeline.py` | **Auto-discovers every model in `models/tasks/`**. For each model: (1) `get_train_config()` returns valid structure; (2) full pipeline: load fixture data → `train()` → `predict()` → `save()` → `load()` |
| `test_model_train.py` | `SeanergysSklearnModel(RandomForest)` trains on FData fixture, `is_trained=True`, history returned |
| `test_model_save_load.py` | Model saves to disk and reloads correctly |

---

## Auto-Discovery: How New Models Are Tested Automatically

The key design principle: **when a developer adds a new model, no test code needs to change**.

`tests/conftest.py` runs `_collect_model_classes()` at pytest collection time:

```
pytest starts
  → conftest.py imports
  → _collect_model_classes() scans models/tasks/**/*.py
  → finds MACK, MCBound, JPCP (and any future models)
  → stores in MODEL_CLASSES dict
  → test_model_pipeline.py parametrizes over MODEL_CLASSES
  → pytest generates one test per model automatically
```

For this to work, a new model must:
1. Subclass `SeanergysModel` and implement `train()`, `predict()`, `save()`, `load()`
2. Implement `get_train_config()` returning `Dict[str, Tuple[model, DatasetClass, (ds_params, dl_params)]]`
3. The dataset must support `is_dummy=True` to load without full Zenodo data in CI

---

## What is `is_dummy=True`?

### The problem

The real datasets in this project are large and hosted on Zenodo:

| Dataset | Size | Source |
|---|---|---|
| `FDataDataset` | ~24 million jobs | Zenodo download |
| `PM100Dataset` | ~231K jobs | Zenodo download |

Downloading and processing this data every time CI runs a test would take minutes,
require network access, and make the pipeline slow and fragile. Tests need to be
fast and work offline.

### What `is_dummy` is

`is_dummy` is a boolean field defined on the `SeanergysDataset` base class:

```python
is_dummy: Optional[bool] = Field(default=False)
```

Every dataset inherits it. When set to `True` it is a signal to the dataset:
**"do not load the real data — give me just enough rows to run the code."**

### What it should do

The correct implementation generates a tiny synthetic DataFrame in memory —
no file, no network, no Zenodo:

```python
# Good implementation of is_dummy in FooDataset
def _load_data_impl(self) -> None:
    if self.is_dummy:
        import pandas as pd
        # 5 synthetic rows — enough to run train/predict/save/load
        self._df = pd.DataFrame({
            "feature_a": [1.0, 2.0, 3.0, 4.0, 5.0],
            "feature_b": [10.0, 20.0, 30.0, 40.0, 50.0],
            "target":    [0, 1, 0, 1, 0],
        })
    else:
        # Normal path — load from file or Zenodo
        self._df = pd.read_parquet(self.data_path)
```

### Current state in this project (Francesco's implementation)

Francesco implemented `is_dummy` in `FDataDataset` like this:

```python
if self.is_dummy:
    self.files = "21-04"                          # load 1 file instead of all
    self.filters += [("adt", "<=", "2021-04-02")] # narrow to 2 days
```

This still downloads from Zenodo or reads a parquet file — it just applies
aggressive filters to get a smaller subset. **This is why CI tests that use
`is_dummy=True` still fail when there is no network or no local file.**
It has been flagged to Francesco in `docs/COLLEAGUE_FEEDBACK.md` (item 6.3).

### Where `is_dummy` is used in the CI pipeline

| Where | What it does |
|---|---|
| `SeanergysDataset` base class | Defines the `is_dummy` field (default `False`) |
| `SeanergysDatasetParams` | Carries `is_dummy` through the config system |
| `test_model_pipeline.py` | Sets `ds_params.is_dummy = True` before running the full pipeline test |
| `test_datasets_smoke.py` | Calls `dataset_cls(**params, is_dummy=True)` in `test_dataset_dummy_mode` |
| `test_datasets_load.py` | Uses `is_dummy=True` in both dummy-mode and Zenodo load tests |
| `validate_models.py` (old, deleted) | Francesco's original script set `dataset_config.is_dummy = True` manually |

### `get_dummy_params()` — the companion method

`is_dummy=True` tells the dataset *how* to load. `get_dummy_params()` tells the
test *what constructor arguments to pass*. They work together:

```python
# CI test does this:
params = FooDataset.get_dummy_params()
# returns {"input_features": ["feature_a"], "output_features": ["target"]}

dataset = FooDataset(**params, is_dummy=True)
dataset.load_data()
# → 5 synthetic rows, no network needed
```

Without `get_dummy_params()`, the test does not know which columns to request
and skips with a message. Without `is_dummy=True` working correctly, the dataset
tries to load real data and fails in CI.

### Summary

| Term | Meaning |
|---|---|
| `is_dummy=False` (default) | Load the real dataset from file or Zenodo |
| `is_dummy=True` | Load a tiny synthetic subset for CI — no network, no file |
| `get_dummy_params()` | Returns the constructor kwargs the test needs to instantiate the dataset |
| Together | Allow any dataset to be tested automatically in CI without any real data |

---

## How to Add a New Model or Dataset — Full Example

This section shows exactly what a developer must do when adding a new model and dataset
so that CI picks them up automatically with zero changes to any test or CI file.

---

### Example: adding `FooDataset` and `FooModel`

#### Step 1 — Create the dataset

```python
# seanergys_modelzoo/datasets/foo_dataset.py

from seanergys_modelzoo.datasets.common.seanergys_dataset import SeanergysDataset

class FooDataset(SeanergysDataset):

    def _load_data_impl(self) -> None:
        if self.is_dummy:
            # No network, no file — generate tiny synthetic data for CI
            import pandas as pd
            self._df = pd.DataFrame({
                "feature_a": [1.0, 2.0, 3.0, 4.0, 5.0],
                "feature_b": [10.0, 20.0, 30.0, 40.0, 50.0],
                "target":    [0, 1, 0, 1, 0],
            })
        else:
            # Real loading from file or Zenodo
            import pandas as pd
            self._df = pd.read_parquet(self.data_path)

    def __len__(self):
        return len(self._df)

    def __getitem__(self, idx):
        row = self._df.iloc[idx]
        x = row[["feature_a", "feature_b"]].values
        y = row["target"]
        return x, y

    @classmethod
    def get_dummy_params(cls) -> dict:
        # Called by CI — returns the minimum params needed to instantiate this dataset
        return {
            "input_features":  ["feature_a", "feature_b"],
            "output_features": ["target"],
        }
```

**What CI does automatically after this file is added:**

```
pytest starts
  → conftest._collect_dataset_classes() scans datasets/
  → finds FooDataset
  → test_dataset_discovery        PASS  (found >= 1 dataset)
  → test_dataset_dummy_mode[FooDataset]
        calls get_dummy_params()  → {"input_features": [...], "output_features": [...]}
        FooDataset(**params, is_dummy=True)
        load_data()               → uses the synthetic DataFrame, no network
        len(dataset) > 0          PASS
        dataset[0]                PASS
  → test_dataset_loads_with_dummy[FooDataset]   PASS
  → test_dataset_loads_from_zenodo[FooDataset]  SKIP (use_zenodo_url not set yet)
```

If `get_dummy_params()` is missing or returns `None`, CI reports:
```
SKIPPED  test_dataset_dummy_mode[FooDataset]
  FooDataset.get_dummy_params() is not implemented.
  Implement it to enable CI testing without network access.
```

---

#### Step 2 — Create the model

```python
# seanergys_modelzoo/models/tasks/foo_task/foo_model/foo_model.py

from seanergys_modelzoo.models.common.seanergys_model import SeanergysModel, SeanergysModelTask
from seanergys_modelzoo.models.common.seanergys_configurator import (
    SeanergysDatasetParams, SeanergysDataloaderParams
)
from seanergys_modelzoo.datasets.foo_dataset import FooDataset

class FooModel(SeanergysModel):

    task_type = SeanergysModelTask.CLASSIFICATION

    def build_model(self): ...
    def train(self, train_data_loader, val_data_loader=None, **kwargs): ...
    def predict(self, data_loader, **kwargs): ...
    def save(self, path, **kwargs): ...

    @classmethod
    def load(cls, path, **kwargs): ...

    @classmethod
    def get_train_config(cls) -> dict:
        model = cls()
        dataset_params = SeanergysDatasetParams(
            input_features=["feature_a", "feature_b"],
            output_features=["target"],
        )
        loader_params = SeanergysDataloaderParams(batch_size=2)
        return {
            "foo_config": (model, FooDataset, (dataset_params, loader_params))
        }
```

**What CI does automatically after this file is added:**

```
pytest starts
  → conftest._collect_model_classes() scans models/tasks/
  → finds FooModel
  → test_model_discovery              PASS
  → test_model_instantiation[FooModel] PASS

  → test_get_train_config_structure[FooModel]
        config = FooModel.get_train_config()
        checks dict is non-empty           PASS
        checks model has train/predict/save/load  PASS
        checks DatasetClass is SeanergysDataset subclass  PASS

  → test_full_pipeline[FooModel]
        config = FooModel.get_train_config()
        ds_params.is_dummy = True
        FooDataset.from_config(ds_params)   → uses synthetic DataFrame
        load_data()                          PASS
        model.train(loader)                  PASS  is_trained=True
        model.predict(loader)                PASS  len(predictions) > 0
        model.save(tmp_path)                 PASS
        FooModel.load(tmp_path)              PASS
```

If `is_dummy=True` does not work in `FooDataset` (e.g. tries to read a file that doesn't exist):
```
SKIPPED  test_full_pipeline[FooModel]
  FooModel/foo_config: dataset setup failed — FileNotFoundError: no such file ...
  Ensure FooDataset supports is_dummy=True without network access.
```

---

#### Summary — the CI contract

| What you must implement | Where | What happens if missing |
|---|---|---|
| `get_dummy_params()` on dataset | Dataset class | All dataset smoke + load tests skip |
| `is_dummy=True` loads data without network | Dataset `_load_data_impl` | Integration pipeline test skips |
| `get_train_config()` on model | Model class | Integration pipeline test is never generated |
| `train / predict / save / load` methods | Model class | Smoke instantiation or pipeline test fails |

**No changes to any test file or CI file are ever needed when adding a new model or dataset.**
The CI contract is entirely defined by the interfaces above.

---

## CI Pipeline (GitLab)

Every push to any branch triggers the full pipeline. There are 4 stages that run in order.
If any non-`allow_failure` job fails, the pipeline stops.

```
push → sanity → validate → lint → test
```

### Stage 1: Sanity (always runs, blocks pipeline on failure)

| Job | What it does | Fails pipeline? |
|---|---|---|
| `sanity:python-syntax` | Compiles every `.py` file with `python -m py_compile`. Catches syntax errors immediately. | Yes |
| `sanity:check-structure` | Checks that `pyproject.toml`, `seanergys_modelzoo/`, `ci/`, `tests/` all exist. | Yes |
| `sanity:check-secrets` | Scans code for accidentally committed secrets (API keys, passwords, tokens). | No (warning) |

### Stage 2: Validate (always runs)

| Job | What it does | Fails pipeline? |
|---|---|---|
| `validate:yaml-json` | Parses all `.yml`, `.yaml`, `.json` files. Catches broken config files including `.gitlab-ci.yml` itself. | Yes |

### Stage 3: Lint (always runs, all are warnings)

| Job | What it does | Fails pipeline? |
|---|---|---|
| `lint:python` | Ruff checks for unused imports, undefined names, duplicate code, bad patterns. | No (warning) |
| `lint:format` | Ruff format check — flags files that need reformatting. | No (warning) |
| `lint:mypy` | Type checking with `--ignore-missing-imports` (heavy ML deps not installed in this job). | No (warning) |

Lint jobs are all `allow_failure: true` because Francesco's files currently have lint
warnings. Once those are fixed, these can be changed to `allow_failure: false`.

### Stage 4: Test (always runs)

| Job | What it does | Fails pipeline? | Install deps |
|---|---|---|---|
| `test:unit` | `pytest tests/unit/` — fast, no I/O | Yes | `--with dev` |
| `test:smoke` | `pytest tests/smoke/` — discovery + instantiation | Yes | `--with dev` |
| `test:import-check` | `python -c "from seanergys_modelzoo..."` — basic import works | Yes | `--with dev,ci` |
| `test:smoke-models` | `pytest tests/smoke/test_models_smoke.py` — model discovery + instantiation | Yes | `--with dev,ci` |
| `test:smoke-datasets` | `pytest tests/smoke/test_datasets_smoke.py` — dataset discovery | Yes | `--with dev,ci` |
| `test:integration` | `pytest tests/integration/` — full pipeline with fixture data | Yes | `--with dev,ci` |
| `test:audit` | pip-audit: scans all dependencies for known CVEs | No (warning) | base only |

#### Why two smoke jobs?

- `test:smoke` installs only `--with dev` (fast, light deps) and runs all smoke tests
- `test:smoke-models` and `test:smoke-datasets` install `--with dev,ci` (heavy ML deps)
  so they can actually import torch, sklearn, xgboost etc. and test real model classes

#### Integration test setup

`test:integration` runs `scripts/create_sample_data.py` before pytest to create local
fixture files. The script then uses those local files — no network needed during the
actual test run.

#### Why sample data is created per model, not per dataset

You might expect the script to discover datasets directly and create a sample for each.
The problem is that `input_features` and `output_features` are **required** fields with
no default — the dataset cannot be instantiated without them:

```python
# This will fail — input_features and output_features are required
FDataDataset(use_zenodo_url=True, is_dummy=True)  # ← ValueError: field required
```

The script has no way to know which columns to pass for an arbitrary dataset class.
That information only exists in two places:

| Where | Status |
|---|---|
| `get_dummy_params()` on the dataset | Not implemented by Francesco — tests skip |
| `get_train_config()` on the model | Already implemented — defines features and params |

So the script uses **models as the entry point**:

1. **Auto-discover** every `SeanergysModel` subclass in `models/tasks/`
2. Call `get_train_config()` on each — already defines `dataset_cls`, `input_features`, `output_features`, filters, etc.
3. **Deduplicate by dataset class** — if MACK and MCBound both use `FDataDataset`, it is downloaded only once
4. Override `ds_params` with `is_dummy=True` — the dataset loads a small filtered subset from Zenodo
5. Save `dataset._df.head(max_rows)` to `tests/fixtures/sample_data/sample_<name>.parquet`

When a developer adds a new model with `get_train_config()`, its dataset fixture is created
automatically — no changes needed in this script.

**Limitation:** if a dataset is added without any model yet, this script will not cover it.
In that case `get_dummy_params()` must be implemented on the dataset class — see
`docs/COLLEAGUE_FEEDBACK.md §6.1`.

---

## Dependency Groups

`pyproject.toml` defines two dependency groups:

| Group | Installed with | Contains | Used by |
|---|---|---|---|
| `dev` | `--with dev` | pytest, ruff, black, pydantic | unit/smoke tests, linting |
| `ci` | `--with ci` | numpy, pandas, torch, sklearn, xgboost, sentence-transformers, pyarrow | smoke-models, smoke-datasets, integration |

---

## `ci/` Folder — What's Left

After the refactor (removing Francesco's ad-hoc scripts), `ci/` contains only:

| File | Purpose |
|---|---|
| `utils.py` | `retrieve_instances_from_file(path, base_class)` — dynamic class discovery. Used by pytest smoke tests and conftest. |
| `validate_yaml.py` | Parses all YAML/JSON files and reports parse errors. Called directly by GitLab CI. |
| `check_secrets.sh` | Shell script: scans for hardcoded secrets using grep patterns. Called directly by GitLab CI. |

---

## Common Workflows

### Before every push
```bash
make test           # unit + smoke, ~30 seconds
make lint           # check for obvious issues
```

### Before opening a MR
```bash
make sample-data    # if not already done
make test-all       # everything including integration
make format         # auto-fix formatting
```

### When you add a new model
```bash
# Add your model to seanergys_modelzoo/models/tasks/<task>/<name>/
# Implement get_train_config() and is_dummy support
make test-pipeline  # automatically picks up your new model
```

### When you add a new dataset
```bash
# Add your dataset to seanergys_modelzoo/datasets/
make test-smoke     # checks it's discovered
make test-datasets  # checks it loads
```

### Simulate the full CI pipeline locally
```bash
make ci
```
