"""
Integration tests: model save and load round-trip.

Uses FDataDataset from tests/fixtures/sample_data/ (run `make sample-data`).
"""

import pytest


def test_model_save_load_roundtrip(fdata_dataset, temp_model_dir):
    """
    Train, save, load, predict. Validates save/load round-trip.
    """
    pytest.importorskip("sklearn")
    pytest.importorskip("torch")
    pytest.importorskip("joblib")

    from sklearn.ensemble import RandomForestRegressor

    from seanergys_modelzoo.dataloader.seanergys_dataloader import SeanergysDataloader
    from seanergys_modelzoo.models.common.seanergys_model import SeanergysModelTask
    from seanergys_modelzoo.models.common.seanergys_model_metadata import (
        SeanergysModelMetadata,
    )
    from seanergys_modelzoo.models.common.sklearn_seanergys_model import (
        SeanergysSklearnModel,
    )

    model = SeanergysSklearnModel(
        model_class=RandomForestRegressor,
        task_type=SeanergysModelTask.REGRESSION,
        model_hyperparameters={"n_estimators": 5, "max_depth": 2},
        metadata=SeanergysModelMetadata(name="TestRegressor"),
    )

    data_loader = SeanergysDataloader(dataset=fdata_dataset, batch_size=4)
    model.train(train_data_loader=data_loader)
    pred_before = model.predict(data_loader)

    save_path = temp_model_dir
    result = model.save(path=save_path)
    assert result is True

    loaded = SeanergysSklearnModel.load(path=save_path)
    assert loaded.is_trained is True
    pred_after = loaded.predict(data_loader)

    assert len(pred_before) == len(pred_after)
    # Predictions should match for the same model
    for a, b in zip(pred_before, pred_after, strict=True):
        assert a == b
