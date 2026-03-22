"""
Integration tests: full pipeline per auto-discovered model.

For every concrete SeanergysModel subclass found in models/tasks/:
  1. Call get_train_config() — the model's own declared training recipe
  2. Override dataset config: is_dummy=True + local fixture file if available
  3. Run: train → predict → save → load

When a developer adds a new model and implements get_train_config(), this
test picks it up automatically — no changes to CI needed.

Fixture files are in tests/fixtures/sample_data/ (create with `make sample-data`).
Tests skip gracefully if fixture data or heavy deps (torch, sentence-transformers)
are not available.
"""

import pytest

from tests.conftest import MODEL_CLASSES

# Map dataset class names to fixture file names.
# Extend this when new datasets are added.
_DATASET_FIXTURE_MAP = {
    "FDataDataset": "sample_fdata.parquet",
    "PM100Dataset": "sample_pm100.parquet",
}


def _resolve_fixture_path(dataset_cls, sample_data_dir):
    """Return local fixture path for a dataset class, or None if not mapped."""
    name = dataset_cls.__name__
    filename = _DATASET_FIXTURE_MAP.get(name)
    if filename is None:
        return None
    path = sample_data_dir / filename
    return path if path.exists() else None


# ---------------------------------------------------------------------------
# Test 1: get_train_config() returns a valid structure
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("model_name,model_cls", list(MODEL_CLASSES.items()))
def test_get_train_config_structure(model_name, model_cls):
    """
    get_train_config() must return a non-empty dict where each entry is
    (model_instance, dataset_class, (dataset_params, dataloader_params)).
    """
    pytest.importorskip("sklearn")

    config = model_cls.get_train_config()

    assert isinstance(config, dict), (
        f"{model_name}.get_train_config() must return a dict"
    )
    assert len(config) > 0, f"{model_name}.get_train_config() returned empty dict"

    for entry_name, entry in config.items():
        assert len(entry) == 3, (
            f"{model_name}/{entry_name}: expected (model, dataset_cls, (ds_params, dl_params))"
        )
        model_instance, dataset_cls, params = entry
        assert len(params) == 2, (
            f"{model_name}/{entry_name}: params must be (dataset_params, dataloader_params)"
        )

        # Model instance has the required interface
        for method in ("train", "predict", "save", "load"):
            assert hasattr(model_instance, method), (
                f"{model_name} is missing required method: {method}"
            )

        # Dataset class is a proper subclass
        from seanergys_modelzoo.datasets.common.seanergys_dataset import (
            SeanergysDataset,
        )

        assert issubclass(dataset_cls, SeanergysDataset), (
            f"{model_name}/{entry_name}: dataset_cls must subclass SeanergysDataset"
        )


# ---------------------------------------------------------------------------
# Test 2: full pipeline — train → predict → save → load
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("model_name,model_cls", list(MODEL_CLASSES.items()))
def test_full_pipeline(model_name, model_cls, tmp_path, sample_data_dir):
    """
    Full pipeline for each discovered model using its own get_train_config().

    Steps:
      - Set is_dummy=True on dataset config (limits data volume)
      - Use local fixture file if available, else skip
      - train() → predict() → save() → load()
    """
    pytest.importorskip("sklearn")
    pytest.importorskip("torch")

    from seanergys_modelzoo.dataloader.seanergys_dataloader import SeanergysDataloader

    config = model_cls.get_train_config()

    for entry_name, (
        model_instance,
        dataset_cls,
        (ds_params, dl_params),
    ) in config.items():
        # Use is_dummy to reduce data volume
        ds_params.is_dummy = True

        # Override data source to local fixture (avoids Zenodo download in CI)
        fixture_path = _resolve_fixture_path(dataset_cls, sample_data_dir)
        if fixture_path is not None:
            ds_params.data_path = fixture_path
            ds_params.use_zenodo_url = False
        else:
            pytest.skip(
                f"{model_name}/{entry_name}: no local fixture for {dataset_cls.__name__}."
                " Run `make sample-data` to create fixture files."
            )

        # Load dataset
        try:
            dataset = dataset_cls.from_config(ds_params)
            dataset.load_data()
        except Exception as e:
            pytest.skip(f"{model_name}/{entry_name}: dataset setup failed — {e}")

        if len(dataset) == 0:
            pytest.skip(f"{model_name}/{entry_name}: dataset is empty after load")

        loader = SeanergysDataloader.from_config(
            data_loader_config=dl_params, dataset=dataset
        )

        # Train
        history = model_instance.train(loader)
        assert model_instance.is_trained, (
            f"{model_name}: is_trained must be True after train()"
        )
        assert history is not None, f"{model_name}: train() must return a history dict"

        # Predict
        predictions = model_instance.predict(loader)
        assert predictions is not None, f"{model_name}: predict() returned None"
        assert len(predictions) > 0, f"{model_name}: predict() returned empty result"

        # Save
        save_path = tmp_path / model_name / entry_name
        save_path.mkdir(parents=True)
        saved = model_instance.save(str(save_path / "model"))
        assert saved, f"{model_name}: save() must return True"

        # Load
        loaded_model = type(model_instance).load(str(save_path / "model"))
        assert loaded_model is not None, f"{model_name}: load() returned None"
