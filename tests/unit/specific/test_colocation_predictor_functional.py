from pathlib import Path

import numpy as np
import pytest
from sklearn.dummy import DummyRegressor
from sklearn.model_selection import cross_val_score
from sklearn.pipeline import Pipeline

from seanergys_modelzoo.dataloader.seanergys_dataloader import SeanergysDataloader
from seanergys_modelzoo.datasets.colocation import ColocationDataset
from seanergys_modelzoo.models.common.seanergys_model import SeanergysModelTask
from seanergys_modelzoo.models.tasks.colocation_prediction.colocation_predictor.colocation_predictor_model import (
    MODEL_CLASSES,
    SCALED_MODELS,
    TECHNOLOGIES,
    ColocationPredictor,
    build_combinations,
    build_model,
    evaluate_technology,
    results_table,
    select_best_technology,
    with_fixed_params,
)

_ROOT = Path(__file__).resolve().parents[3]
FIXTURE = _ROOT / "tests" / "fixtures" / "sample_data" / "sample_colocation.parquet"

pytestmark = pytest.mark.skipif(
    not FIXTURE.exists(), reason=f"fixture missing: {FIXTURE}"
)

# Ridge (full 56-config grid) + XGBoost with n_estimators shrunk to one value.
FAST = {"technologies": ["Ridge Regression", "XGBoost"], "n_estimators": 5, "n_jobs": 1}


def _loader(split) -> SeanergysDataloader:
    dataset = ColocationDataset(
        data_path=str(FIXTURE),
        split=split,
        input_features=list(ColocationPredictor.FEATURES),
        output_features=[ColocationPredictor.TARGET],
    )
    return SeanergysDataloader(dataset=dataset, batch_size=1)


def _xy(split):
    X, y = ColocationPredictor()._extract_data_from_loader(_loader(split))
    return X, y.ravel()


def test_defaults_follow_the_notebook():
    model = ColocationPredictor()
    assert model.task_type == SeanergysModelTask.REGRESSION
    assert model.supported_datasets == [ColocationDataset]
    assert model.hyperparameters == {
        "technologies": TECHNOLOGIES,
        "cv_folds": 5,
        "n_jobs": -1,
        "n_estimators": None,
    }
    assert isinstance(model.estimator, DummyRegressor)
    assert model.best_technology is None


def test_unknown_hyperparameter_rejected():
    with pytest.raises(ValueError, match="Unknown ColocationPredictor hyperparameters"):
        ColocationPredictor(model_hyperparameters={"model_name": "XGBoost"})


@pytest.mark.parametrize("technologies", [[], ["Linear Regression"]])
def test_invalid_technologies_rejected(technologies):
    with pytest.raises(ValueError, match="Invalid technologies"):
        ColocationPredictor(model_hyperparameters={"technologies": technologies})


def test_generic_test_hyperparameters_are_accepted():
    ColocationPredictor(model_hyperparameters={"n_jobs": 1})
    ColocationPredictor(model_hyperparameters={"n_estimators": 2, "n_jobs": 1})


def test_grid_sizes_match_the_notebook():
    sizes = {technology: len(grid) for technology, grid in build_combinations().items()}
    assert sizes == {
        "Random Forests": 160,
        "Multi-Layer Perceptron": 2160,
        "Support Vector Machine": 288,
        "Ridge Regression": 56,
        "K-Nearest Neighbors": 768,
        "Gradient Boosting Machine": 1280,
        "XGBoost": 144,
    }


def test_n_estimators_shrinks_only_the_ensemble_grids():
    full, small = (
        build_combinations(),
        ColocationPredictor(model_hyperparameters={"n_estimators": 5}).model_specs(),
    )
    for technology in ("Random Forests", "Gradient Boosting Machine", "XGBoost"):
        assert {c["n_estimators"] for c in small[technology]} == {5}
        assert len(small[technology]) * 4 == len(full[technology])
    for technology in (
        "Support Vector Machine",
        "Ridge Regression",
        "K-Nearest Neighbors",
    ):
        assert small[technology] == full[technology]


def test_svm_grid_only_varies_degree_and_coef0_for_poly():
    grid = build_combinations()["Support Vector Machine"]
    for kernel in ("linear", "rbf"):
        rows = [c for c in grid if c["kernel"] == kernel]
        assert {(c["degree"], c["coef0"]) for c in rows} == {(3, 0.0)}
    poly = [c for c in grid if c["kernel"] == "poly"]
    assert {(c["degree"], c["coef0"]) for c in poly} == {
        (2, 0.0),
        (2, 0.5),
        (3, 0.0),
        (3, 0.5),
    }


@pytest.mark.parametrize("technology", list(MODEL_CLASSES))
def test_build_model_scales_only_the_notebooks_scaled_models(technology):
    model = build_model(technology, {})
    if technology in SCALED_MODELS:
        assert isinstance(model, Pipeline)
        assert list(model.named_steps) == ["scaler", "model"]
        assert isinstance(model.named_steps["model"], MODEL_CLASSES[technology])
    else:
        assert isinstance(model, MODEL_CLASSES[technology])


def test_fixed_params_per_technology():
    assert with_fixed_params("Random Forests", {"a": 1}) == {"a": 1, "random_state": 1}
    assert with_fixed_params("Gradient Boosting Machine", {}) == {"random_state": 1}
    assert with_fixed_params("Multi-Layer Perceptron", {}) == {
        "random_state": 1,
        "max_iter": 500,
    }
    assert with_fixed_params("XGBoost", {}) == {
        "random_state": 1,
        "objective": "reg:squarederror",
        "eval_metric": "rmse",
        "n_jobs": 1,
    }
    for technology in (
        "Support Vector Machine",
        "Ridge Regression",
        "K-Nearest Neighbors",
    ):
        assert with_fixed_params(technology, {"a": 1}) == {"a": 1}


def test_evaluate_technology_picks_the_lowest_cv_mae():
    X, y = _xy("train")
    X_val, y_val = _xy("test")
    grid = build_combinations()["Ridge Regression"]
    scores = [
        -cross_val_score(
            build_model("Ridge Regression", c),
            X,
            y,
            cv=5,
            scoring="neg_mean_absolute_error",
        ).mean()
        for c in grid
    ]
    best = int(np.argmin(scores))

    model, info = evaluate_technology(
        "Ridge Regression", grid, X, y, X_val, y_val, n_jobs=1
    )
    assert info["model_name"] == f"Model_{best}"
    assert info["params"] == grid[best]
    assert info["performance"]["CV_MAE"] == pytest.approx(scores[best])
    preds = model.predict(X_val)
    assert info["performance"]["MAE"] == pytest.approx(np.mean(np.abs(preds - y_val)))
    assert info["training_time"] >= 0 and info["inference_time"] >= 0


def test_evaluate_technology_without_validation_data():
    X, y = _xy("train")
    _, info = evaluate_technology(
        "Ridge Regression", build_combinations()["Ridge Regression"][:3], X, y, n_jobs=1
    )
    assert info["performance"]["MAE"] is None and info["inference_time"] is None


def test_select_best_and_results_table():
    info = {
        "A": {
            "model_name": "Model_1",
            "params": {},
            "performance": {"CV_MAE": 0.3, "MAE": 1, "RMSE": 1, "R2": 0},
            "training_time": 1,
            "inference_time": 1,
        },
        "B": {
            "model_name": "Model_2",
            "params": {},
            "performance": {"CV_MAE": 0.1, "MAE": 1, "RMSE": 1, "R2": 0},
            "training_time": 1,
            "inference_time": 1,
        },
    }
    assert select_best_technology(info) == "B"
    assert [row["Model"] for row in results_table(info)] == ["B", "A"]


def test_train_selects_the_technology_with_the_lowest_cv_mae():
    model = ColocationPredictor(model_hyperparameters=FAST)
    history = model.train(_loader("train"))
    info = model.estimator.all_models_info_
    assert set(info) == {"Ridge Regression", "XGBoost"}
    best = min(info, key=lambda t: info[t]["performance"]["CV_MAE"])
    assert model.best_technology == best == history["best_technology"]
    assert not isinstance(model.estimator, DummyRegressor)
    X_val, y_val = _xy("test")
    preds = model.estimator.predict(X_val)
    assert info[best]["performance"]["RMSE"] == pytest.approx(
        np.sqrt(np.mean((preds - y_val) ** 2))
    )
    assert [row["Model"] for row in history["results"]] == sorted(
        info, key=lambda t: info[t]["performance"]["CV_MAE"]
    )


def test_train_uses_an_explicit_validation_loader():
    model = ColocationPredictor(
        model_hyperparameters={**FAST, "technologies": ["Ridge Regression"]}
    )
    model.train(_loader("train"), _loader("train"))
    X, y = _xy("train")
    preds = model.estimator.predict(X)
    assert model.estimator.best_model_info_["performance"]["MAE"] == pytest.approx(
        np.mean(np.abs(preds - y))
    )


def test_train_without_a_split_has_no_validation_metrics():
    model = ColocationPredictor(
        model_hyperparameters={**FAST, "technologies": ["Ridge Regression"]}
    )
    model.train(_loader(None))
    assert model.estimator.best_model_info_["performance"]["MAE"] is None


def test_predict_after_training():
    model = ColocationPredictor(model_hyperparameters=FAST)
    model.train(_loader("train"))
    preds = model.predict(_loader("test"))
    assert preds.shape == (len(_loader("test").dataset),)
    assert np.isfinite(preds).all()


def test_mlflow_extras_after_training():
    model = ColocationPredictor(model_hyperparameters=FAST)
    assert model.mlflow_extras() == {"params": {}, "metrics": {}, "dicts": {}}
    model.train(_loader("train"))
    extras = model.mlflow_extras()
    best = model.estimator.best_model_info_
    assert extras["params"]["best_technology"] == model.best_technology
    assert extras["params"]["best_configuration"] == best["model_name"]
    assert extras["metrics"]["cv_mae"] == best["performance"]["CV_MAE"]
    assert [row["Model"] for row in extras["dicts"]["results.json"]][
        0
    ] == model.best_technology


def test_save_and_load_roundtrip(tmp_path):
    model = ColocationPredictor(model_hyperparameters=FAST)
    model.train(_loader("train"))
    expected = model.predict(_loader("test"))
    assert model.save(tmp_path / "model")
    restored = ColocationPredictor.load(tmp_path / "model")
    np.testing.assert_allclose(restored.predict(_loader("test")), expected)
    assert restored.best_technology == model.best_technology


def test_train_and_test_configs_use_the_random_hold_out():
    (_, ds_cls, (ds_params, _)) = ColocationPredictor.get_train_config()["colocation"]
    assert ds_cls is ColocationDataset
    assert ds_params.split == "train"
    assert ds_params.use_zenodo_url is True
    assert ds_params.input_features == ColocationPredictor.FEATURES
    assert ds_params.output_features == ["SpeedupA"]


def test_invalid_dataset_name_rejected():
    with pytest.raises(Exception, match="Invalid dataset name"):
        ColocationPredictor.get_train_config(dataset_name="scaling")
    with pytest.raises(Exception, match="Invalid dataset name"):
        ColocationPredictor.get_test_config(
            ColocationPredictor(), dataset_name="scaling"
        )
