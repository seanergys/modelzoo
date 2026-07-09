from seanergys_modelzoo.models.tasks.duration_prediction.duration_prediction_bull.models.duration_model import (
    DurationModel,
)
import pytest
import numpy as np


def test_metadata_contains_units():
    model = DurationModel()

    model.metadata = {
        "target_unit": "minutes",
        "walltime_unit": "minutes",
    }

    assert model.metadata["target_unit"] == "minutes"
    assert model.metadata["walltime_unit"] == "minutes"


def test_get_weights_sum_to_one():
    model = DurationModel()
    model.val_rmse = [1.0, 2.0, 4.0]

    weights = model._get_weights()

    assert np.isclose(weights.sum(), 1.0)


def test_get_weights_favor_best_model():
    model = DurationModel()
    model.val_rmse = [1.0, 10.0]

    weights = model._get_weights()

    assert weights[0] > weights[1]


def test_predict_without_training_raises():
    model = DurationModel()

    with pytest.raises(RuntimeError):
        model.predict(np.zeros((1, 10)))


class DummyModel:
    def __init__(self, value):
        self.value = value

    def predict(self, X):
        return np.full(X.shape[0], self.value)


def test_weighted_ensemble_prediction():
    model = DurationModel()

    model.models = [
        DummyModel(10.0),
        DummyModel(20.0),
    ]

    model.val_rmse = [1.0, 2.0]

    X = np.zeros((5, 3))

    pred = model.predict(X)

    expected = ((1.0 / 1.0) * 10.0 + (1.0 / 2.0) * 20.0) / ((1.0 / 1.0) + (1.0 / 2.0))

    assert np.allclose(pred, expected)


def test_predict_full_contains_required_keys():
    model = DurationModel()

    model.models = [DummyModel(10.0)]
    model.val_rmse = [1.0]

    X = np.zeros((2, 3))

    result = model.predict_full(X)

    assert "y_pred" in result
    assert "uncertainty" in result
    assert "members" in result
    assert "y_pred_best" in result
    assert "best_model_idx" in result


def test_save_and_load(tmp_path):
    model = DurationModel()

    assert model.save(tmp_path)

    loaded = DurationModel.load(tmp_path)

    assert isinstance(loaded, DurationModel)
