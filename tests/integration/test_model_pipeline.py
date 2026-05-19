"""
Integration tests: full pipeline per (model, dataset) pair.

For every (model_cls, dataset_id) pair discovered via supported_datasets:
  1. test_get_train_config_structure — get_train_config(dataset_id) returns valid structure
  2. test_full_pipeline             — train → predict → save → load

Both tests are fully dynamic. No model or dataset names are hardcoded.
Adding a new model and declaring its supported_datasets automatically adds it here.

CI contract for model authors:
  - Declare supported_datasets in _inject_defaults (list of dataset classes with DATASET_ID)
  - Implement get_train_config(dataset_name) returning
      Dict[str, Tuple[model, DatasetClass, (SeanergysDatasetParams, SeanergysDataloaderParams)]]
  - Ensure the dataset supports is_dummy=True so CI does not need real data or network
"""

import os

import pytest

from tests.conftest import MODEL_DATASET_PAIRS

_PAIR_IDS = [f"{m.__name__}-{d}" for m, d in MODEL_DATASET_PAIRS]


# ---------------------------------------------------------------------------
# Test 1: get_train_config(dataset_id) returns a valid structure
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("model_cls,dataset_name", MODEL_DATASET_PAIRS, ids=_PAIR_IDS)
def test_get_train_config_structure(model_cls, dataset_name):
    """
    get_train_config(dataset_name) must return a dict with the entry for that dataset:
      { dataset_name: (model_instance, DatasetClass, (SeanergysDatasetParams, SeanergysDataloaderParams)) }

    Also checks that the model instance has all required interface methods.
    """
    pytest.importorskip("sklearn")

    from seanergys_modelzoo.datasets.common.seanergys_dataset import SeanergysDataset
    from seanergys_modelzoo.models.common.seanergys_configurator import (
        SeanergysDataloaderParams,
        SeanergysDatasetParams,
    )

    model_name = model_cls.__name__
    config = model_cls.get_train_config(dataset_name)

    assert isinstance(config, dict), (
        f"{model_name}.get_train_config({dataset_name!r}) must return a dict"
    )
    assert dataset_name in config, (
        f"{model_name}.get_train_config({dataset_name!r}) did not return entry for {dataset_name!r}"
    )

    model_instance, dataset_cls, params = config[dataset_name]
    assert len(params) == 2, (
        f"{model_name}/{dataset_name}: third element must be (SeanergysDatasetParams, SeanergysDataloaderParams)"
    )
    ds_params, dl_params = params

    for method in ("train", "predict", "save", "load"):
        assert hasattr(model_instance, method), (
            f"{model_name} is missing required method: {method}"
        )

    assert issubclass(dataset_cls, SeanergysDataset), (
        f"{model_name}/{dataset_name}: DatasetClass must subclass SeanergysDataset, "
        f"got {dataset_cls}"
    )
    assert isinstance(ds_params, SeanergysDatasetParams), (
        f"{model_name}/{dataset_name}: ds_params must be SeanergysDatasetParams, "
        f"got {type(ds_params)}"
    )
    assert isinstance(dl_params, SeanergysDataloaderParams), (
        f"{model_name}/{dataset_name}: dl_params must be SeanergysDataloaderParams, "
        f"got {type(dl_params)}"
    )


# ---------------------------------------------------------------------------
# Test 2: full pipeline — train → predict → save → load
# ---------------------------------------------------------------------------


@pytest.mark.zenodo
@pytest.mark.parametrize("model_cls,dataset_name", MODEL_DATASET_PAIRS, ids=_PAIR_IDS)
def test_full_pipeline(model_cls, dataset_name, tmp_path):
    """
    Full pipeline for each (model, dataset) pair using get_train_config(dataset_name).

    Uses is_dummy=True on the dataset config. NOTE: some datasets still download from
    Zenodo with filters when is_dummy=True, so network access may be required.

    Skip with: CI_SKIP_ZENODO=1 make test-integration

    Skips if the dataset does not support is_dummy=True properly (len == 0 or load fails).
    This skip is a signal to the dataset author to implement is_dummy support.
    """
    if os.environ.get("CI_SKIP_ZENODO") == "1":
        pytest.skip("SKIP: CI_SKIP_ZENODO=1 — Zenodo tests disabled for this run.")

    pytest.importorskip("sklearn")
    pytest.importorskip("torch")

    from seanergys_modelzoo.dataloader.seanergys_dataloader import SeanergysDataloader

    model_name = model_cls.__name__
    config = model_cls.get_train_config(dataset_name)
    model_instance, dataset_cls, (ds_params, dl_params) = config[dataset_name]

    ds_params.is_dummy = True

    try:
        dataset = dataset_cls.from_config(ds_params)
        dataset.load_data()
    except Exception as e:
        pytest.skip(
            f"{model_name}/{dataset_name}: dataset setup failed — {e}. "
            f"Ensure {dataset_cls.__name__} supports is_dummy=True without network access."
        )

    if len(dataset) == 0:
        pytest.skip(
            f"{model_name}/{dataset_name}: dataset returned 0 samples with is_dummy=True. "
            f"Implement is_dummy support in {dataset_cls.__name__} to enable this test."
        )

    loader = SeanergysDataloader.from_config(
        data_loader_config=dl_params, dataset=dataset
    )

    history = model_instance.train(loader)
    assert model_instance.is_trained, (
        f"{model_name}: is_trained must be True after train()"
    )
    assert history is not None, (
        f"{model_name}: train() must return a history dict, got None"
    )

    predictions = model_instance.predict(loader)
    assert predictions is not None, f"{model_name}: predict() returned None"
    assert len(predictions) > 0, f"{model_name}: predict() returned empty result"

    save_path = tmp_path / model_name / dataset_name
    save_path.mkdir(parents=True)
    saved = model_instance.save(str(save_path / "model"))
    assert saved, f"{model_name}: save() must return True"

    loaded_model = type(model_instance).load(str(save_path / "model"))
    assert loaded_model is not None, f"{model_name}: load() returned None"
