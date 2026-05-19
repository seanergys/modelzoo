# DATASET_ID and supported_datasets — Why They Exist
_seanergys-modelzoo | Author: Mohsen | Updated: 2026-05-19_

This document explains two small additions to the codebase and why they were made.

---

## Background: the problem with the old integration tests

The integration test `test_model_pipeline.py` used to parametrize by **model only**:

```python
@pytest.mark.parametrize("model_cls", MODEL_CLASSES)
def test_full_pipeline(model_cls):
    config = model_cls.get_train_config()   # default: dataset_name="f-data"
    for entry_name, (...) in config.items():
        ...  # internal loop over datasets
```

This had two problems:

1. **JPCP was only half-tested.** JPCP supports both `f-data` and `pm100`, but
   `get_train_config()` with no argument defaults to `"f-data"`. The `pm100` path
   was never exercised in CI.

2. **Failures were hard to read.** If JPCP failed on `pm100`, pytest reported
   `FAILED test_full_pipeline[JPCP]` — you couldn't tell which dataset caused it.

---

## The fix: one test per (model, dataset) pair

The integration tests are now parametrized by **(model, dataset)** pair:

```
test_full_pipeline[MACK-f-data]
test_full_pipeline[MCBound-f-data]
test_full_pipeline[JPCP-f-data]
test_full_pipeline[JPCP-pm100]       ← this was invisible before
```

To generate these pairs automatically, CI needs to know:
- **Which datasets does each model support?** → `supported_datasets`
- **What string key does each dataset use in `get_train_config()`?** → `DATASET_ID`

---

## Change 1 — `supported_datasets` in model validators

`supported_datasets` is a field on `SeanergysModel` that lists the dataset classes
a model can work with. JPCP already set it. MACK and MCBound did not — they have been
updated:

```python
# mack_model.py and mcbound_model.py — _inject_defaults
values.setdefault("supported_datasets", [FDataDataset])
```

**Rule:** every new model you add must set `supported_datasets` in its `_inject_defaults`
validator. This is how CI discovers what to test.

---

## Change 2 — `DATASET_ID` on dataset classes

`DATASET_ID` is a `ClassVar[str]` on `SeanergysDataset`. It must equal the dict key
that `get_train_config()` uses for that dataset.

```python
class FDataDataset(SeanergysParquetDataset):
    DATASET_ID: ClassVar[str] = "f-data"   # matches get_train_config key

class PM100Dataset(SeanergysParquetDataset):
    DATASET_ID: ClassVar[str] = "pm100"    # matches get_train_config key
```

### Why not use the existing `metadata["dataset_name"]`?

The `metadata` dict already stored names like `"F-DATA"` and `"PM100"`, but it
could not be used here for two reasons:

- It is **instance-level** — it is set inside `validate_model()` and requires a
  fully instantiated dataset object. `DATASET_ID` is a class-level constant readable
  without any instantiation.
- The **values don't match** — `metadata["dataset_name"]` is `"F-DATA"` (uppercase),
  but `get_train_config()` expects `"f-data"` (lowercase). Using it would break the lookup.

---

## Contract for adding new models and datasets

### Adding a new dataset

1. Set `DATASET_ID` to the exact string your model's `get_train_config()` uses as the dict key.

```python
class MyNewDataset(SeanergysParquetDataset):
    DATASET_ID: ClassVar[str] = "my-dataset"   # must match get_train_config key
```

### Adding a new model

1. Declare `supported_datasets` in `_inject_defaults`:

```python
@model_validator(mode="before")
@classmethod
def _inject_defaults(cls, values):
    values.setdefault("supported_datasets", [FDataDataset, MyNewDataset])
    ...
    return values
```

2. Implement `get_train_config(dataset_name)` with a branch for each supported dataset,
   using the same string keys as the `DATASET_ID` values:

```python
@classmethod
def get_train_config(cls, dataset_name: str = "f-data", get_dummy_data: bool = False):
    if dataset_name == "f-data":
        return {"f-data": (...)}
    if dataset_name == "my-dataset":
        return {"my-dataset": (...)}
    raise Exception(f"Dataset {dataset_name} not supported.")
```

CI will automatically pick up the new (model, dataset) pairs — no changes needed in
`conftest.py` or the test files.
