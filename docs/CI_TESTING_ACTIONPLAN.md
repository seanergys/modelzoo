# CI Testing Action Plan & Decision Log
_Author: Mohsen | Created: 2026-03-22_

---

## Summary

This document records the full conversation, decisions, and rationale behind the CI testing
refactor for `seanergys-modelzoo`. It covers what Francesco (colleague) built, why it was
insufficient as a CI solution, and how Mohsen improved it using proper CI best practices.

---

## 1. What Francesco Built (main branch)

Francesco developed three Python scripts without knowledge of CI concepts:

### Files (now deleted from `scripts/tests/` in main, originally at):
- `scripts/tests/validate_models.py`
- `scripts/tests/validate_datasets.py`
- `tests/seanergys_model_evaluator.py`

### What each did

**`validate_models.py`**
- Manually discovered all `SeanergysModel` subclasses by doing `rglob("*.py")` and dynamically importing them
- Called `model_class.get_train_config()` to get the training configuration defined by each model
- Set `dataset_config.is_dummy = True` to load a small data subset
- Manually ran `model_instance.train(dataloader_instance)` in a loop
- Caught exceptions manually and called `sys.exit(0)` or `sys.exit(1)`

**`validate_datasets.py`**
- Discovered all `SeanergysDataset` subclasses via `rglob`
- Did **nothing** with them after discovery — just exited 0
- No functional validation at all

**`seanergys_model_evaluator.py`**
- A class `SeanergysModelEvaluator` that wraps a model and runs: train → predict → save → load
- Auto-selects metrics based on task type (MSE/MAE/R² for regression, accuracy/F1 for classification)
- Was never called by any script or test — dead code

### Francesco's key insight (good idea, wrong implementation)
The `get_train_config()` method — defined on each model — returns the model instance + dataset
class + full config (dataset params + dataloader params). This is the right hook: each model
declares how it should be trained. Francesco's approach of using this for validation was correct
in concept. The problem was implementation: he wrote it as ad-hoc Python scripts instead of
using a proper testing framework.

### What was missing
- No CI pipeline (no `.gitlab-ci.yml`)
- No pytest — all test logic written manually
- No pyproject.toml / Poetry
- No linting, formatting, type checking
- `validate_datasets.py` did no actual validation
- `seanergys_model_evaluator.py` was never wired into anything
- Scripts lived in `scripts/tests/` — not a standard location

---

## 2. The Three Files Mohsen Inherited (temp folder / older draft)

During the conversation, three files were found at `/home/mohsen/scratch/SEANERGYS/temp/`:
- `validate_models.py`
- `validate_datasets.py`
- `seanergys_model_evaluator.py`

These were **older drafts** of Francesco's scripts. The versions in `ci/` on Mohsen's branch
were already cleaner refactors. Key differences from the temp (old) versions:

| Area | Temp (old) | ci/ (refactored on Mohsen's branch) |
|---|---|---|
| `validate_models.py` imports | `scripts.utils`, `tests.seanergys_model_evaluator` | `ci.utils` only |
| Model validation call | Manual training loop | `model_class.run_dummy_validation()` (broken — method doesn't exist) |
| `validate_datasets.py` discovery | `os.listdir` + nested structure, bare `except:` | `rglob`, skips `__init__.py`, warns on errors |
| Formatting | Single quotes, loose types | Black-formatted, proper type hints |

The temp files are outdated and were safely discarded.

---

## 3. What Mohsen's Branch Added (ci/add-gitlab-pipeline)

Mohsen's branch (`ci/add-gitlab-pipeline`) added proper CI infrastructure on top of
Francesco's model/dataset code (which was left untouched):

| Added | Purpose |
|---|---|
| `.gitlab-ci.yml` | Full pipeline: sanity → validate → lint → unit → smoke → integration |
| `ci/validate_models.py` | Refactored discovery script (but had a bug — see Section 4) |
| `ci/validate_datasets.py` | Refactored discovery script (still no functional validation) |
| `ci/utils.py` | `retrieve_instances_from_file`, `import_module_from_file` — genuinely useful |
| `ci/validate_yaml.py` | YAML/JSON config validation |
| `ci/check_secrets.sh` | Secret scanning |
| `ci/seanergys_model_evaluator.py` | Moved + reformatted from `tests/` |
| `tests/unit/` | U1–U6: utils, logger, configurator, dataset contract, metadata, dataloader params |
| `tests/smoke/` | Model/dataset discovery, instantiation, dataset load from fixture |
| `tests/integration/` | Train + save/load using `SeanergysSklearnModel(RandomForest)` on FData fixture |
| `tests/fixtures/sample_data/` | `sample_fdata.parquet`, `sample_pm100.parquet` |
| `pyproject.toml` | Poetry, ruff, black, mypy, pytest config |
| `Makefile` | `make test`, `make lint`, `make sample-data` |

---

## 4. Problems Found in Mohsen's Branch (before fix)

### Problem 1 — `validate_models.py` calls a non-existent method
`ci/validate_models.py` was changed to call `model_class.run_dummy_validation()`.
This method **does not exist** in the `SeanergysModel` base class. It would crash for
every model at runtime.

### Problem 2 — `validate_datasets.py` still does no functional validation
Despite being refactored, it still only discovered dataset classes and exited 0.
No `__len__`, `__getitem__`, or `is_dummy` check was performed. Useless as a CI gate.

### Problem 3 — `SeanergysModelEvaluator` is dead code in `ci/`
It was moved to `ci/seanergys_model_evaluator.py` but nothing imported or called it.

### Problem 4 — Integration tests only cover `SeanergysSklearnModel`
The integration tests were written against the sklearn base wrapper with RandomForest,
not against the actual models in `models/tasks/` (MACK, MCBound, JPCP). New models
added by developers were not automatically tested.

---

## 5. The Key Decision: Delete the Three CI Scripts

### Question asked
> "Why do I need to keep these three files if I can do the same thing with pytest and CI?"

### Answer
You don't. Those three files exist because Francesco didn't know pytest.
He manually re-implemented what pytest does for free:

| Francesco's script | pytest equivalent |
|---|---|
| `rglob` + dynamic import to discover classes | `conftest.py` parametrized fixture |
| `try/except` + `sys.exit(1)` on failure | test failure with full traceback |
| `logger.info(...)` progress output | pytest `-v` output |
| Manual `is_dummy` loop | fixture setup with `is_dummy=True` |
| `seanergys_model_evaluator.py` orchestration | regular test function |

### Decision
**Delete from `ci/`:**
- `ci/validate_models.py` — replaced by pytest smoke + integration tests
- `ci/validate_datasets.py` — replaced by pytest smoke + integration tests
- `ci/seanergys_model_evaluator.py` — logic inlined into pytest integration test

**Keep in `ci/`:**
- `ci/utils.py` — `retrieve_instances_from_file` is genuinely useful, used by pytest smoke tests
- `ci/validate_yaml.py` — different purpose, not replaceable by pytest
- `ci/check_secrets.sh` — shell script, different purpose

**GitLab CI calls `pytest` directly**, not custom scripts, for all model/dataset validation.

---

## 6. Issues to Communicate to Francesco (do NOT change his code)

These are notes to share with Francesco so he can improve his model/dataset code.
Mohsen's CI branch should not touch these files.

| # | File | Issue | Suggested fix |
|---|------|-------|---------------|
| C1 | `seanergys_model.py` | `get_dummy_params()` returns `None` (just `pass`) | Should raise `NotImplementedError` so subclasses are forced to implement it, or return a sensible default |
| C2 | `seanergys_model.py` | `get_train_config()` return type hint is wrong: `Dict[Tuple[...]]` | Should be `Dict[str, Tuple[...]]` |
| C3 | `seanergys_dataset.py` | `get_dummy_params()` also returns `None` | Same as C1 |
| C4 | `f_data.py` | `is_dummy=True` still loads from Zenodo (just filters to a smaller date range). In CI without network access this will fail | Provide a local fallback or make `is_dummy` use a tiny synthetic DataFrame |
| C5 | `mack_model.py` | `get_train_config()` hardcodes `use_zenodo_url=True` — CI without network fails | Support a local `data_path` override |
| C6 | `seanergys_model_evaluator.py` | Was placed in `tests/` (non-standard) | Already moved to `ci/` in Mohsen's branch; will be deleted as part of the refactor |
| C7 | `scripts/tests/validate_models.py` | Imports from `tests.seanergys_model_evaluator` (hardcoded path) | Use relative import or move to a proper package |

---

## 7. Final Architecture (after refactor)

### Repository layout (CI-relevant files)

```
ci/
  utils.py            ← keep: retrieve_instances_from_file used by pytest
  validate_yaml.py    ← keep: YAML/JSON validation, not replaceable by pytest
  check_secrets.sh    ← keep: secret scanning

tests/
  conftest.py         ← session-scoped model discovery fixture (parametrized)
  unit/               ← fast, no I/O, synthetic data
    test_utils.py
    test_logger.py
    test_configurator.py
    test_dataset_contract.py
    test_metadata.py
    test_dataloader_params.py
  smoke/              ← import, discover, instantiate — no training
    test_models_smoke.py
    test_datasets_smoke.py
    test_datasets_load.py
  integration/        ← full pipeline: train → predict → save → load
    conftest.py
    test_model_pipeline.py   ← KEY: parametrized over all discovered models
    test_model_train.py
    test_model_save_load.py
  fixtures/
    sample_data/
      sample_fdata.parquet
      sample_pm100.parquet
```

### GitLab CI pipeline

```
sanity      → syntax check, repo structure, secret scan     (shell)
validate    → ci/validate_yaml.py                           (shell)
lint        → ruff, black, mypy                             (shell)
unit        → pytest tests/unit/                            (every push)
smoke       → pytest tests/smoke/                           (every push)
integration → pytest tests/integration/                     (MR + model/dataset changes)
```

### Key design rule
> When a developer adds a new model to `seanergys_modelzoo/models/tasks/`, they must:
> 1. Implement the `SeanergysModel` interface: `build_model`, `train`, `predict`, `save`, `load`
> 2. Implement `get_train_config()` returning model instance + dataset class + config
> 3. Ensure the dataset supports `is_dummy=True` for CI runs without real data downloads
>
> If they do these three things, pytest auto-discovers and tests their model automatically.
> **No CI code changes needed when a new model is added.**

---

## 8. Test Checklist (current status after decisions)

### DevOps
- [x] D1 Syntax check
- [x] D2 Repo structure check
- [x] D3 Lint (ruff)
- [x] D4 Format (black)
- [x] D5 Type check (mypy, allow_failure)
- [x] D6 Config/YAML validation
- [x] D7 Dependency audit (pip-audit)
- [x] D8 Import sanity
- [x] D9 Secret scan
- [ ] D10 Docs build (optional)

### Unit
- [x] U1 Discovery utils
- [x] U2 Logger
- [x] U3 Configurator
- [x] U4 Dataset contract (synthetic class)
- [x] U5 Model metadata
- [x] U6 Dataloader params

### Smoke
- [x] S1 Model discovery
- [x] S2 Model instantiation
- [x] S3 Dataset discovery
- [x] S4 Dataset load from fixture
- [ ] S5 Model–dataset compatibility (model.supported_datasets exist)
- [ ] S6 Parametrized model fixture in conftest
- [ ] S7 Dataset dummy-mode instantiation

### Integration
- [x] I1 Train (SeanergysSklearnModel only — needs to cover all models)
- [x] I2 Predict (SeanergysSklearnModel only — needs to cover all models)
- [x] I3 Save/load
- [ ] I4 Full pipeline per auto-discovered model (train→predict→save→load)
- [ ] I5 Model–dataset pair fixtures per real model
- [ ] I6 Train produces numeric metrics assertion

### CI Scripts (after refactor)
- [x] YAML validation
- [x] Secret scan
- [x] `ci/utils.py` used by pytest
- [x] Three ad-hoc scripts deleted (validate_models, validate_datasets, seanergys_model_evaluator)

### E2E (future — when ML pipeline exists)
- [ ] E1–E5 Full pipeline, model registry, inference, reproducibility

---

## 9. Next Immediate Steps

1. Delete `ci/validate_models.py`, `ci/validate_datasets.py`, `ci/seanergys_model_evaluator.py`
2. Update `.gitlab-ci.yml` to remove any jobs that called those scripts
3. Add `tests/integration/test_model_pipeline.py` — parametrized over all discovered models
4. Implement parametrized model fixture in `tests/conftest.py`
5. Share `docs/CI_TESTING_ACTIONPLAN.md` Section 6 with Francesco as feedback
