# Integration Tests

## What Do They Do?

Integration tests check that the modelzoo pieces work together end-to-end on real data (F-DATA parquet). They use `tests/fixtures/sample_data/` — create it first with `make sample-data`.

### 1. `test_model_train_on_fixture_data`
Trains a RandomForestRegressor on F-DATA for one epoch. Checks that `train()` finishes without errors and that `is_trained` is True.

### 2. `test_model_predict_after_train`
Trains a model, then calls `predict()`. Checks that predictions are returned and that the number of predictions matches the dataset size.

### 3. `test_model_save_load_roundtrip`
Trains a model, saves it to a temp dir, loads it back, and predicts again. Checks that the loaded model gives the same predictions as the original.

---

## Warnings from `make test-integration`

| Warning | Meaning |
|--------|---------|
| **`datetime.utcnow() is deprecated`** | Code uses `datetime.utcnow()` instead of `datetime.now(datetime.UTC)`. Safe for now but will break in future Python. Fix in `seanergys_model_metadata.py` and Pydantic. |
| **`A custom validator is returning a value other than self`** | A Pydantic model validator returns a new object instead of mutating `self`. Pydantic v2 prefers returning `self`. Comes from `SeanergysSklearnModel` and the test files that instantiate it. |
| **`NumPy array is not writable`** | The dataset yields a read-only NumPy array; PyTorch prefers writable tensors. Can be fixed by copying the array before converting to tensor. |
| **`A column-vector y was passed when a 1d array was expected`** | Target `y` is shaped as `(n, 1)` but scikit-learn expects `(n,)`. Use `.ravel()` on `y` before fitting. |

All tests pass. These warnings do not stop the tests but are worth fixing to avoid future breakage.
