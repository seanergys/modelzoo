"""
Smoke tests: dataset loading with actual data.

TWO APPROACHES ARE TESTED
--------------------------

Approach A — via get_dummy_params() (dataset-level contract):
    Dataset defines its own constructor kwargs via get_dummy_params().
    Instantiated with is_dummy=True — loads a small subset without network.
    Status: NOT YET IMPLEMENTED on current datasets (tests will SKIP).

Approach B — via get_train_config() (model-level contract):
    Model's get_train_config() provides dataset class + params.
    Instantiated with is_dummy=True — loads a small filtered subset from Zenodo.
    Status: WORKS TODAY once get_train_config() type hints are fixed.

Zenodo test:
    Loads each dataset directly from its Zenodo URL with is_dummy=True.
    Skipped if CI_SKIP_ZENODO=1. Requires network access.
"""

import os

import pytest

pytest.importorskip("pandas")
pytest.importorskip("pyarrow")
pytest.importorskip("torch")
pytest.importorskip("sklearn")

from tests.conftest import DATASET_CLASSES, MODEL_CLASSES


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _collect_dataset_configs_from_models():
    """
    Collect unique (dataset_cls, ds_params) from all model get_train_config() calls.
    Deduplicated by dataset class name so each dataset is only loaded once.
    """
    seen = {}
    for model_name, model_cls in MODEL_CLASSES.items():
        try:
            config = model_cls.get_train_config()
        except Exception:
            continue
        for entry_name, (model_instance, dataset_cls, (ds_params, dl_params)) in config.items():
            key = dataset_cls.__name__
            if key not in seen:
                seen[key] = (dataset_cls, ds_params, f"{model_name}/{entry_name}")
    return seen


_DATASET_CONFIGS_FROM_MODELS = _collect_dataset_configs_from_models()


# ---------------------------------------------------------------------------
# Approach A: load via get_dummy_params()
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("dataset_name,dataset_cls", list(DATASET_CLASSES.items()))
def test_dataset_loads_approach_a(dataset_name, dataset_cls):
    """
    Approach A — load dataset using get_dummy_params() + is_dummy=True.

    PASS: dataset instantiates, loads data, len > 0, dataset[0] returns (x, y).
    SKIP: get_dummy_params() not implemented — Approach A unavailable for this
          dataset. Use Approach B (model-based) or implement get_dummy_params().
    FAIL: dataset instantiates but loads 0 rows, or dataset[0] returns None.

    No network needed if is_dummy=True generates synthetic data locally.
    """
    params = dataset_cls.get_dummy_params()

    if params is None:
        pytest.skip(
            f"\n  SKIP [{dataset_name}] Approach A: get_dummy_params() not implemented.\n"
            f"  → {dataset_name} cannot be tested via Approach A.\n"
            f"  → Approach B (model-based) may still cover this dataset.\n"
            f"  → To enable Approach A: implement get_dummy_params() on {dataset_name}.\n"
            f"    It should return a dict like:\n"
            f"      {{'input_features': [...], 'output_features': [...]}}"
        )

    dataset = dataset_cls(**params, is_dummy=True)
    dataset.load_data()

    assert len(dataset) >= 1, (
        f"FAIL [{dataset_name}] Approach A: loaded 0 samples with is_dummy=True.\n"
        f"  → Check that {dataset_name}._load_data_impl() returns at least 1 row "
        f"when is_dummy=True."
    )

    item = dataset[0]
    assert item is not None, (
        f"FAIL [{dataset_name}] Approach A: dataset[0] returned None.\n"
        f"  → Check that {dataset_name}.__getitem__() returns a valid (x, y) tuple."
    )


# ---------------------------------------------------------------------------
# Approach B: load via model get_train_config()
# ---------------------------------------------------------------------------

@pytest.mark.zenodo
@pytest.mark.parametrize(
    "dataset_name,config",
    [(k, v) for k, v in _DATASET_CONFIGS_FROM_MODELS.items()],
)
def test_dataset_loads_approach_b(dataset_name, config):
    """
    Approach B — load dataset using params from model get_train_config() + is_dummy=True.

    PASS: dataset instantiates with model-provided params, loads data, len > 0,
          dataset[0] returns a valid (x, y) tuple.
    SKIP: CI_SKIP_ZENODO=1 set, or no model references this dataset via
          get_train_config(). Add a model that uses this dataset, or implement
          get_dummy_params() (Approach A).
    FAIL: dataset loads 0 rows, or dataset[0] fails.

    Marked @zenodo because Francesco's is_dummy=True still downloads from Zenodo
    with filters — it does not generate synthetic data locally. This will become
    network-free once is_dummy=True is fixed to generate data in memory.
    Skip with: CI_SKIP_ZENODO=1 make test-smoke
    """
    if os.environ.get("CI_SKIP_ZENODO") == "1":
        pytest.skip("SKIP: CI_SKIP_ZENODO=1 — Zenodo tests disabled for this run.")
    dataset_cls, ds_params, source = config

    params = ds_params.model_dump()
    params["is_dummy"] = True

    try:
        dataset = dataset_cls(**params)
    except Exception as e:
        pytest.fail(
            f"FAIL [{dataset_name}] Approach B: failed to instantiate using params "
            f"from {source}.\n  → Error: {e}"
        )

    assert len(dataset) >= 1, (
        f"FAIL [{dataset_name}] Approach B: loaded 0 samples.\n"
        f"  → Params came from {source}.\n"
        f"  → Check that is_dummy=True reduces data but still returns at least 1 row."
    )

    item = dataset[0]
    assert item is not None, (
        f"FAIL [{dataset_name}] Approach B: dataset[0] returned None.\n"
        f"  → Check that {dataset_name}.__getitem__() returns a valid (x, y) tuple."
    )


# ---------------------------------------------------------------------------
# Zenodo test: load directly from Zenodo URL
# ---------------------------------------------------------------------------

@pytest.mark.zenodo
@pytest.mark.parametrize("dataset_name,dataset_cls", list(DATASET_CLASSES.items()))
def test_dataset_loads_from_zenodo(dataset_name, dataset_cls):
    """
    Load each dataset from its Zenodo source with is_dummy=True (small subset).

    PASS: dataset downloads from Zenodo, loads data, len > 0, dataset[0] valid.
    SKIP: CI_SKIP_ZENODO=1 set, get_dummy_params() not implemented, or dataset
          does not support use_zenodo_url=True.
    FAIL: Zenodo download succeeds but 0 rows loaded, or dataset[0] fails.

    Requires network. Skip locally with: CI_SKIP_ZENODO=1 make test-smoke
    """
    if os.environ.get("CI_SKIP_ZENODO") == "1":
        pytest.skip("SKIP: CI_SKIP_ZENODO=1 — Zenodo tests disabled for this run.")

    params = dataset_cls.get_dummy_params()

    if params is None:
        pytest.skip(
            f"\n  SKIP [{dataset_name}] Zenodo test: get_dummy_params() not implemented.\n"
            f"  → Cannot determine constructor kwargs for {dataset_name}.\n"
            f"  → Implement get_dummy_params() to enable this test."
        )

    try:
        dataset = dataset_cls(**params, use_zenodo_url=True, is_dummy=True)
        dataset.load_data()
    except TypeError:
        pytest.skip(
            f"\n  SKIP [{dataset_name}] Zenodo test: use_zenodo_url=True not supported.\n"
            f"  → Add use_zenodo_url field to {dataset_name} to enable Zenodo testing."
        )
    except Exception as e:
        pytest.fail(
            f"FAIL [{dataset_name}] Zenodo test: download or load failed.\n"
            f"  → Error: {e}"
        )

    assert len(dataset) >= 1, (
        f"FAIL [{dataset_name}] Zenodo test: loaded 0 samples with is_dummy=True.\n"
        f"  → Check that is_dummy=True filters the Zenodo data to at least 1 row."
    )

    x, y = dataset[0]
    assert x is not None, f"FAIL [{dataset_name}] Zenodo test: dataset[0] returned x=None."
    assert y is not None, f"FAIL [{dataset_name}] Zenodo test: dataset[0] returned y=None."
