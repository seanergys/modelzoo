# Code Review Feedback for Francesco
_Prepared by Mohsen | 2026-03-22_

Hi Francesco,

While setting up the CI pipeline I ran automated code quality checks (ruff linter, ruff formatter,
mypy type checker) across the whole codebase. Below is a list of issues found in your files.
None of these break functionality right now, but they will cause the CI lint job to report
warnings on every push. It would be great if you could address them when you have time.

I have not touched your files — all changes are yours to make.

---

## 1. Formatting (ruff format)

The following files need to be reformatted to match the project's code style (Black-compatible).
You can fix all of them at once by running:

```bash
ruff format seanergys_modelzoo
```

**Files that need reformatting:**
- `seanergys_modelzoo/datasets/common/seanergys_dataset.py`
- `seanergys_modelzoo/datasets/f_data.py`
- `seanergys_modelzoo/datasets/pm100.py`
- `seanergys_modelzoo/models/common/seanergys_model.py`
- `seanergys_modelzoo/models/tasks/performance_prediction/mack/mack_model.py`
- `seanergys_modelzoo/models/tasks/performance_prediction/mcbound/mcbound_model.py`
- `seanergys_modelzoo/models/tasks/power_consumption_prediction/jpcp/jpcp_model.py`

---

## 2. Unused Imports (ruff check)

These imports are defined but never used in the file. They add noise and slow down imports.
You can auto-fix most of them by running:

```bash
ruff check --fix seanergys_modelzoo
```

| File | Unused import | How to fix |
|------|--------------|------------|
| `seanergys_dataset.py` | `field_validator` from pydantic | Remove it from the import line |
| `f_data.py` | `os`, `Any`, `Iterable`, `SeanergysLogger` | Remove them from their import lines |
| `seanergys_model.py` | `Literal`, `pickle`, `SeanergysModelConfiguration` | Remove them from their import lines |
| `mack_model.py` | `pickle`, `Iterable`, `SeanergysModelParams` | Remove them from their import lines |
| `mcbound_model.py` | `SeanergysModelParams`, `SeanergysDataloader`, `SeanergysModel` | Remove them from their import lines |
| `jpcp_model.py` | `time`, `Callable`, `Iterable`, `Type`, `SeanergysModel` | Remove them from their import lines |

---

## 3. Duplicate Method Definition in `mack_model.py`

**File:** `seanergys_modelzoo/models/tasks/performance_prediction/mack/mack_model.py`

`transform_embeddings` is defined **twice** in the `MACK` class — once at line 69 and again
at line 143. Python silently uses only the second definition, which means the first one
(line 69) is completely ignored. This is almost certainly a bug.

```python
# Line 69 — this version is silently ignored
def transform_embeddings(self, features: np.ndarray) -> np.ndarray:
    ...

# Line 143 — this is the one Python actually uses
def transform_embeddings(self, features: np.ndarray, encoder_weights: str = "...") -> np.ndarray:
    ...
```

**What to do:** Decide which version is correct and remove the other one. If both are needed,
give them different names.

---

## 4. Duplicate Import in `mcbound_model.py`

**File:** `seanergys_modelzoo/models/tasks/performance_prediction/mcbound/mcbound_model.py`

`Enum` is imported twice:

```python
from enum import Enum   # line 7
...
from enum import Enum   # line 12 — duplicate, remove this one
```

**What to do:** Remove the second `from enum import Enum` line.

---

## 5. f-strings Without Placeholders

Several log calls use an `f"..."` string but have no `{variable}` inside them. This is
harmless but pointless — the `f` prefix does nothing.

```python
# Wrong — f prefix does nothing here
model.logger.info(f"Training on FData")

# Correct
model.logger.info("Training on FData")
```

**Files affected:**
- `mack_model.py` — lines 166, 225
- `mcbound_model.py` — line 141
- `jpcp_model.py` — lines 118, 139, 170, 191

Auto-fixable with:

```bash
ruff check --fix seanergys_modelzoo
```

---

## 6. Design Issues (not caught by linter — needs discussion)

These are not linter errors but design gaps that will cause problems in CI and for other
developers using your code.

### 6.1 `get_dummy_params()` returns `None`

**Files:** `seanergys_modelzoo/datasets/common/seanergys_dataset.py`,
`seanergys_modelzoo/models/common/seanergys_model.py`

Both base classes define `get_dummy_params()` as:

```python
@classmethod
def get_dummy_params(cls) -> dict:
    pass  # returns None implicitly
```

This means any code that calls `get_dummy_params()` expecting a dict will silently get `None`
and crash later in a confusing way. It should either raise `NotImplementedError` (forcing
subclasses to implement it) or return a sensible default.

**Suggested fix:**
```python
@classmethod
def get_dummy_params(cls) -> dict:
    raise NotImplementedError(
        f"{cls.__name__} must implement get_dummy_params() "
        "to support dummy/CI validation mode."
    )
```

### 6.2 `get_train_config()` return type hint is wrong

**Files:** `mack_model.py`, `jpcp_model.py`, `mcbound_model.py`

The return type is annotated as `Dict[Tuple[...]]` but a `Dict` needs two type parameters:
key type and value type. It should be `Dict[str, Tuple[...]]` since the keys are strings
like `"fdata"`, `"pm100"`.

```python
# Wrong
def get_train_config(cls) -> Dict[Tuple["MACK", SeanergysDataset, ...]]:

# Correct
def get_train_config(cls) -> Dict[str, Tuple["MACK", SeanergysDataset, ...]]:
```

### 6.3 `is_dummy=True` still downloads from Zenodo

**Files:** `f_data.py`, and all models that call `get_train_config()`

When `is_dummy=True` is set on `FDataDataset`, it narrows the data to a small date range
but still tries to load from a Zenodo URL or a parquet file on disk. In CI (no network,
no pre-downloaded files) this will fail.

The intended purpose of `is_dummy` in CI is: *"load a tiny amount of data without needing
the real dataset"*. The cleanest way to support this is to generate a small synthetic
DataFrame when `is_dummy=True`, instead of trying to load from a file:

```python
def model_post_init(self, __context):
    if self.is_dummy:
        # Generate tiny synthetic data — no file or network needed
        self._data = pd.DataFrame({
            "nnuma": [1, 2, 3, 4, 5],
            "duration": [10.0, 20.0, 30.0, 40.0, 50.0],
            "avgpcon": [100.0, 200.0, 300.0, 400.0, 500.0],
        })
        return
    self.load_data()
```

### 6.4 `get_train_config()` hardcodes `use_zenodo_url=True`

**Files:** `mack_model.py`, `jpcp_model.py`, `mcbound_model.py`

All training configs hardcode `use_zenodo_url=True`, which means CI always tries to
download from the internet. Consider accepting a `data_path` parameter override so that
CI can point to a local fixture file:

```python
@classmethod
def get_train_config(cls, data_path: Optional[Path] = None) -> dict:
    fdata_config = SeanergysDatasetParams(
        use_zenodo_url=data_path is None,
        data_path=data_path,
        ...
    )
```

---

## Summary

| # | Type | Files | Auto-fixable? |
|---|------|-------|--------------|
| 1 | Formatting | 7 files in `seanergys_modelzoo/` | Yes — `ruff format seanergys_modelzoo` |
| 2 | Unused imports | 6 files | Yes — `ruff check --fix seanergys_modelzoo` |
| 3 | Duplicate method | `mack_model.py` | Manual — decide which version to keep |
| 4 | Duplicate import | `mcbound_model.py` | Yes — `ruff check --fix seanergys_modelzoo` |
| 5 | f-strings | `mack_model.py`, `mcbound_model.py`, `jpcp_model.py` | Yes — `ruff check --fix seanergys_modelzoo` |
| 6.1 | `get_dummy_params()` returns None | base classes | Manual |
| 6.2 | Wrong type hint on `get_train_config()` | model files | Manual |
| 6.3 | `is_dummy` still needs network | `f_data.py` | Manual |
| 6.4 | `use_zenodo_url=True` hardcoded | model files | Manual |

**Quick wins** (run these two commands and items 1, 2, 4, 5 are done):
```bash
ruff format seanergys_modelzoo
ruff check --fix seanergys_modelzoo
```

Items 3 and 6.x need manual attention. Happy to discuss any of these.
