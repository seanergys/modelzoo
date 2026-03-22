"""
Smoke tests: dataset discovery and contract validation. No data loading, no network.

TWO APPROACHES ARE TESTED
--------------------------

Approach A — via get_dummy_params() (dataset-level contract):
    Each dataset class implements get_dummy_params() returning the constructor
    kwargs needed to instantiate it. This is the cleanest contract but requires
    Francesco to implement it on each concrete dataset class.
    Status: NOT YET IMPLEMENTED on FDataDataset, PM100Dataset, SCRIPTAIDataset.

Approach B — via get_train_config() (model-level contract):
    Each model implements get_train_config() which already defines which dataset
    class to use and which input/output features to pass. We use this to verify
    the dataset contract without needing get_dummy_params().
    Status: WORKS TODAY — no changes needed from Francesco.

Both approaches are fully dynamic. No dataset or model names are hardcoded.
Adding a new dataset or model is picked up automatically.
"""

import pytest

pytest.importorskip("torch", reason="Dataset discovery requires torch")
pytest.importorskip("sklearn", reason="Model discovery requires sklearn")

from tests.conftest import DATASET_CLASSES, MODEL_CLASSES


# ---------------------------------------------------------------------------
# Test 1: discovery — always runs
# ---------------------------------------------------------------------------

def test_dataset_discovery():
    """
    PASS: at least one SeanergysDataset subclass found in datasets/.
    FAIL: no dataset classes found — check that your dataset file is in
          seanergys_modelzoo/datasets/ and subclasses SeanergysDataset.
    """
    assert len(DATASET_CLASSES) >= 1, (
        "No SeanergysDataset subclasses found in seanergys_modelzoo/datasets/.\n"
        "Make sure your dataset file:\n"
        "  - lives in seanergys_modelzoo/datasets/\n"
        "  - subclasses SeanergysDataset\n"
        "  - is not named __init__.py"
    )


def test_model_discovery():
    """
    PASS: at least one SeanergysModel subclass found in models/tasks/.
    FAIL: no model classes found — check that your model file is in
          seanergys_modelzoo/models/tasks/ and subclasses SeanergysModel.
    """
    assert len(MODEL_CLASSES) >= 1, (
        "No SeanergysModel subclasses found in seanergys_modelzoo/models/tasks/.\n"
        "Make sure your model file:\n"
        "  - lives in seanergys_modelzoo/models/tasks/<task>/<name>/\n"
        "  - subclasses SeanergysModel\n"
        "  - is not named __init__.py"
    )


# ---------------------------------------------------------------------------
# Test 2A — Approach A: dataset contract via get_dummy_params()
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("dataset_name,dataset_cls", list(DATASET_CLASSES.items()))
def test_dataset_contract_via_get_dummy_params(dataset_name, dataset_cls):
    """
    Approach A — dataset-level contract (get_dummy_params).

    PASS: get_dummy_params() returns a dict with input_features and output_features.
    SKIP: get_dummy_params() is not implemented — dataset cannot be auto-tested
          without a model. Add get_dummy_params() to enable this check.
    FAIL: get_dummy_params() returns something other than a dict, or is missing
          required keys (input_features, output_features).

    No data is loaded — this only checks the contract, not actual loading.
    """
    params = dataset_cls.get_dummy_params()

    if params is None:
        pytest.skip(
            f"\n  SKIP [{dataset_name}] Approach A: get_dummy_params() not implemented.\n"
            f"  → The dataset cannot be tested without a model in Approach A.\n"
            f"  → Either implement get_dummy_params() on {dataset_name},\n"
            f"    or rely on Approach B (model-based) which works today.\n"
            f"  → See docs/COLLEAGUE_FEEDBACK.md §6.1 for the implementation guide."
        )

    assert isinstance(params, dict), (
        f"FAIL [{dataset_name}] get_dummy_params() must return a dict, got {type(params)}."
    )
    assert "input_features" in params, (
        f"FAIL [{dataset_name}] get_dummy_params() dict must contain 'input_features'."
    )
    assert "output_features" in params, (
        f"FAIL [{dataset_name}] get_dummy_params() dict must contain 'output_features'."
    )
    assert len(params["input_features"]) >= 1, (
        f"FAIL [{dataset_name}] get_dummy_params()['input_features'] must not be empty."
    )
    assert len(params["output_features"]) >= 1, (
        f"FAIL [{dataset_name}] get_dummy_params()['output_features'] must not be empty."
    )


# ---------------------------------------------------------------------------
# Test 2B — Approach B: dataset contract via model get_train_config()
# ---------------------------------------------------------------------------

def _collect_dataset_configs_from_models():
    """
    Collect unique (dataset_name, dataset_cls, ds_params) from all model
    get_train_config() calls. Deduplicated by dataset class name.
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


@pytest.mark.parametrize(
    "dataset_name,config",
    [(k, v) for k, v in _DATASET_CONFIGS_FROM_MODELS.items()],
)
def test_dataset_contract_via_model_config(dataset_name, config):
    """
    Approach B — model-level contract (get_train_config).

    PASS: get_train_config() on the model provides a valid dataset class with
          input_features, output_features defined — dataset is ready for CI.
    SKIP: no model references this dataset via get_train_config(). Either add
          a model that uses it, or implement get_dummy_params() (Approach A).
    FAIL: dataset_cls or ds_params missing required fields.

    No data is loaded — this only checks the contract, not actual loading.
    """
    dataset_cls, ds_params, source = config

    assert dataset_cls is not None, (
        f"FAIL [{dataset_name}] dataset_cls from {source} is None."
    )
    assert hasattr(ds_params, "input_features"), (
        f"FAIL [{dataset_name}] ds_params from {source} missing input_features."
    )
    assert hasattr(ds_params, "output_features"), (
        f"FAIL [{dataset_name}] ds_params from {source} missing output_features."
    )
    assert len(ds_params.input_features) >= 1, (
        f"FAIL [{dataset_name}] ds_params.input_features from {source} is empty."
    )
    assert len(ds_params.output_features) >= 1, (
        f"FAIL [{dataset_name}] ds_params.output_features from {source} is empty."
    )
