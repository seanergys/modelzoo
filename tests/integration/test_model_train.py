"""
Integration tests: model training on subset data.

Uses FDataDataset from tests/fixtures/sample_data/ (run `make sample-data`).
"""
import pytest


def test_model_train_on_fixture_data(fdata_dataset):
    """
    Train a sklearn-based model on F-DATA fixture for 1 epoch.
    Validates train() runs without error.
    """
    pytest.importorskip("sklearn")
    pytest.importorskip("torch")

    from seanergys_modelzoo.models.common.sklearn_seanergys_model import SeanergysSklearnModel
    from seanergys_modelzoo.models.common.seanergys_model import SeanergysModelTask
    from seanergys_modelzoo.models.common.seanergys_model_metadata import SeanergysModelMetadata
    from seanergys_modelzoo.dataloader.seanergys_dataloader import SeanergysDataloader
    from sklearn.ensemble import RandomForestRegressor

    model = SeanergysSklearnModel(
        model_class=RandomForestRegressor,
        task_type=SeanergysModelTask.REGRESSION,
        model_hyperparameters={"n_estimators": 5, "max_depth": 2},
        metadata=SeanergysModelMetadata(name="TestRegressor"),
    )

    data_loader = SeanergysDataloader(dataset=fdata_dataset, batch_size=4)
    history = model.train(train_data_loader=data_loader)

    assert model.is_trained is True
    assert history is not None
    assert "training" in history
    assert len(fdata_dataset) >= 1


def test_model_predict_after_train(fdata_dataset):
    """
    Train then predict. Validates predict() returns valid output shape.
    """
    pytest.importorskip("sklearn")
    pytest.importorskip("torch")

    from seanergys_modelzoo.models.common.sklearn_seanergys_model import SeanergysSklearnModel
    from seanergys_modelzoo.models.common.seanergys_model import SeanergysModelTask
    from seanergys_modelzoo.models.common.seanergys_model_metadata import SeanergysModelMetadata
    from seanergys_modelzoo.dataloader.seanergys_dataloader import SeanergysDataloader
    from sklearn.ensemble import RandomForestRegressor

    model = SeanergysSklearnModel(
        model_class=RandomForestRegressor,
        task_type=SeanergysModelTask.REGRESSION,
        model_hyperparameters={"n_estimators": 5, "max_depth": 2},
        metadata=SeanergysModelMetadata(name="TestRegressor"),
    )

    data_loader = SeanergysDataloader(dataset=fdata_dataset, batch_size=4)
    model.train(train_data_loader=data_loader)
    predictions = model.predict(data_loader)

    assert predictions is not None
    assert len(predictions) == len(fdata_dataset)
