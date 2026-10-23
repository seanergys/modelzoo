import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from sklearn.linear_model import LinearRegression
from sklearn.pipeline import Pipeline
from xgboost import XGBRegressor

from seanergys_modelzoo.dataloader.seanergys_dataloader import SeanergysDataloader
from seanergys_modelzoo.datasets.scaling import ScalingDataset
from seanergys_modelzoo.models.common.seanergys_model import SeanergysModelTask
from seanergys_modelzoo.models.tasks.scaling_prediction.scaling_predictor.scaling_predictor_model import (
    SUPPORTED_REGRESSORS,
    BootstrapFeatureSelectingXGBRegressor,
    BootstrapFeatureSelector,
    ScalingPredictor,
    build_regressor,
    evaluate_grouped_repeated,
    get_feature_importance,
)

_ROOT = Path(__file__).resolve().parents[3]
FIXTURE = _ROOT / "tests" / "fixtures" / "sample_data" / "sample_scaling.parquet"
ZENODO_URL = ScalingDataset.model_fields["ZENODO_URL"].default

N_STABLE = 5
SMALL_HPARAMS = {
    "n_estimators": 10,
    "random_state": 0,
    "n_jobs": 1,
    "n_bootstrap": 4,
    "n_stable_features": N_STABLE,
    "cv_n_splits": 3,
}
SELECTOR_HPARAMS = {k: v for k, v in SMALL_HPARAMS.items() if k != "cv_n_splits"}

pytestmark = pytest.mark.skipif(
    not FIXTURE.exists(), reason=f"fixture missing: {FIXTURE}"
)


def _dataset(**kwargs) -> ScalingDataset:
    return ScalingDataset(
        data_path=str(FIXTURE),
        input_features=list(ScalingPredictor.CANDIDATE_FEATURES),
        output_features=["Speedup_XZ"],
        **kwargs,
    )


def _loader() -> SeanergysDataloader:
    return SeanergysDataloader(dataset=_dataset(), batch_size=1)


def _xy():
    ds = _dataset()
    X = np.stack([ds[i][0] for i in range(len(ds))])
    y = np.concatenate([ds[i][1] for i in range(len(ds))])
    return X, y


@pytest.fixture(scope="module")
def trained_model() -> ScalingPredictor:
    model = ScalingPredictor(model_hyperparameters=SMALL_HPARAMS)  # type: ignore[call-arg]
    model.train(_loader())
    return model


def test_model_defaults_injected():
    model = ScalingPredictor(model_hyperparameters=SMALL_HPARAMS)
    assert model.model_class is Pipeline
    assert isinstance(model.estimator, Pipeline)
    assert list(model.estimator.named_steps) == ["bootstrap_selector", "regressor"]
    assert isinstance(
        model.estimator.named_steps["bootstrap_selector"], BootstrapFeatureSelector
    )
    assert isinstance(model.estimator.named_steps["regressor"], XGBRegressor)
    assert model.task_type == SeanergysModelTask.REGRESSION
    assert ScalingDataset in model.supported_datasets
    assert model.selected_features is None
    assert model.feature_stability_scores is None
    assert model.grouped_cv_summary is None


def test_defaults_are_the_notebook_settings():
    hp = ScalingPredictor().hyperparameters
    assert hp["model_name"] == "XGBoost"
    assert (hp["n_estimators"], hp["random_state"]) == (300, 42)
    assert (hp["n_bootstrap"], hp["n_stable_features"], hp["epsilon"]) == (
        100,
        20,
        1e-8,
    )
    assert (hp["cv_n_splits"], hp["cv_test_size"]) == (50, 0.2)


def test_hyperparameters_reach_selector_and_regressor():
    est = ScalingPredictor(model_hyperparameters=SMALL_HPARAMS).estimator
    selector = est.named_steps["bootstrap_selector"]
    assert selector.n_bootstrap == SMALL_HPARAMS["n_bootstrap"]
    assert selector.n_stable_features == N_STABLE
    assert est.named_steps["regressor"].n_estimators == SMALL_HPARAMS["n_estimators"]


def test_unknown_hyperparameter_rejected():
    with pytest.raises(ValueError, match="Unknown ScalingPredictor hyperparameters"):
        ScalingPredictor(model_hyperparameters={"n_bootstraps": 5})


@pytest.mark.parametrize("name", SUPPORTED_REGRESSORS)
def test_model_name_selects_regressor(name):
    est = ScalingPredictor(model_hyperparameters={"model_name": name}).estimator
    assert type(est.named_steps["regressor"]) is type(build_regressor(name))


def test_candidate_features_are_unique_and_exclude_target_and_keys():
    candidates = ScalingPredictor.CANDIDATE_FEATURES
    assert len(candidates) == len(set(candidates))
    for leaked in ("Speedup_XZ", "Time_Z", "Benchmark", "Suite_X", "Suite_Y"):
        assert leaked not in candidates


def test_fixture_has_every_candidate_feature_and_target():
    columns = set(pd.read_parquet(FIXTURE).columns)
    missing = set(ScalingPredictor.CANDIDATE_FEATURES + ["Speedup_XZ"]) - columns
    assert not missing


@pytest.mark.zenodo
@pytest.mark.skipif(os.environ.get("CI_SKIP_ZENODO") == "1", reason="CI_SKIP_ZENODO=1")
def test_zenodo_dataset_has_every_candidate_feature_and_target():
    columns = set(pd.read_parquet(ZENODO_URL).columns)
    missing = set(ScalingPredictor.CANDIDATE_FEATURES + ["Speedup_XZ"]) - columns
    assert not missing


def test_default_train_config_uses_whole_dataset_and_all_candidates():
    (_, ds_cls, (ds_params, _)) = ScalingPredictor.get_train_config()["scaling"]
    assert ds_cls is ScalingDataset
    assert ds_params.input_features == ScalingPredictor.CANDIDATE_FEATURES
    assert ds_params.output_features == ["Speedup_XZ"]
    assert ds_params.data_path is None
    assert ds_params.use_zenodo_url is True
    assert not getattr(ds_params, "filters", None)


def test_invalid_dataset_name_rejected():
    with pytest.raises(Exception, match="Invalid dataset name"):
        ScalingPredictor.get_train_config(dataset_name="pm100")


@pytest.mark.parametrize("name", SUPPORTED_REGRESSORS)
def test_get_feature_importance_one_value_per_column(name):
    X, y = _xy()
    model = build_regressor(name, n_estimators=5, random_state=0).fit(X, y)
    importance = get_feature_importance(model, X, y, name, permutation_repeats=2)
    assert importance.shape == (X.shape[1],)
    if name == "LinearRegression":
        np.testing.assert_array_equal(importance, np.abs(model.coef_))


def test_evaluate_grouped_repeated_keeps_groups_apart_and_summarises():
    ds = _dataset()
    X, y = _xy()
    groups = ds.get_groups()
    results, summary = evaluate_grouped_repeated(
        LinearRegression(), X, y, groups, n_splits=4, test_size=0.2
    )
    assert len(results) == 4
    assert set(summary) == {
        f"{m}_{s}" for m in ("MAE", "RMSE", "R2") for s in ("mean", "std")
    }
    assert summary["RMSE_mean"] == pytest.approx(results["RMSE"].mean())
    assert summary["RMSE_std"] == pytest.approx(results["RMSE"].std())
    for test_benchmarks in results["test_benchmarks"]:
        assert test_benchmarks
        assert set(test_benchmarks) <= set(groups)


def test_selector_only_selects_features():
    X, y = _xy()
    selector = BootstrapFeatureSelector(**SELECTOR_HPARAMS).fit(X, y)
    assert not hasattr(selector, "predict")
    assert len(selector.selected_idx_) == N_STABLE
    np.testing.assert_array_equal(selector.transform(X), X[:, selector.selected_idx_])
    for attr in ("mean_importance_", "std_importance_", "feature_stability_"):
        assert getattr(selector, attr).shape == (X.shape[1],)
    np.testing.assert_allclose(
        selector.feature_stability_,
        selector.mean_importance_ / (selector.std_importance_ + selector.epsilon),
    )


def test_selector_matches_notebook_bootstrap_loop():
    from sklearn.base import clone
    from sklearn.utils import resample

    X, y = _xy()
    selector = BootstrapFeatureSelector(**SELECTOR_HPARAMS).fit(X, y)

    rng = np.random.RandomState(SMALL_HPARAMS["random_state"])
    base = XGBRegressor(n_estimators=10, random_state=0, n_jobs=1)
    importances = []
    for _ in range(SMALL_HPARAMS["n_bootstrap"]):
        X_boot, y_boot = resample(
            X, y, replace=True, random_state=rng.randint(0, 100000)
        )
        importances.append(clone(base).fit(X_boot, y_boot).feature_importances_)
    importances = np.array(importances)
    np.testing.assert_allclose(selector.mean_importance_, importances.mean(axis=0))
    np.testing.assert_allclose(selector.std_importance_, importances.std(axis=0))


def test_bootstrap_uses_whole_dataset(monkeypatch):
    seen = {}
    original_fit = BootstrapFeatureSelector.fit

    def spy_selector_fit(self, X, y):
        seen["select_rows"] = len(X)
        return original_fit(self, X, y)

    monkeypatch.setattr(BootstrapFeatureSelector, "fit", spy_selector_fit)
    model = ScalingPredictor(model_hyperparameters=SMALL_HPARAMS)
    loader = _loader()
    model.train(loader)

    assert seen["select_rows"] == len(_dataset())
    regressor = model.estimator.named_steps["regressor"]
    assert regressor.n_features_in_ == N_STABLE
    assert regressor.get_booster().num_features() == N_STABLE
    assert len(loader.dataset) == loader.dataset.stats["n_samples"]


def test_regressor_is_trained_by_scaling_predictor_not_by_the_pipeline(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Pipeline.fit must not be used")

    monkeypatch.setattr(Pipeline, "fit", forbidden)
    model = ScalingPredictor(model_hyperparameters=SMALL_HPARAMS)
    model.train(_loader())
    assert model.is_trained


def test_train_matches_direct_notebook_procedure(trained_model):
    X_all, y_all = _xy()
    X_tr, y_tr = _xy()
    X_te, _ = _xy()

    selector = BootstrapFeatureSelector(**SELECTOR_HPARAMS).fit(X_all, y_all)
    regressor = XGBRegressor(n_estimators=10, random_state=0, n_jobs=1)
    regressor.fit(selector.transform(X_tr), y_tr)

    assert trained_model.estimator.named_steps["bootstrap_selector"].selected_idx_ == (
        selector.selected_idx_
    )
    np.testing.assert_array_equal(
        trained_model.estimator.predict(X_te),
        regressor.predict(selector.transform(X_te)),
    )


def test_grouped_cv_runs_on_selected_features(trained_model):
    summary = trained_model.grouped_cv_summary
    assert set(summary) == {
        f"{m}_{s}" for m in ("MAE", "RMSE", "R2") for s in ("mean", "std")
    }
    splits = trained_model.estimator.grouped_cv_["splits"]
    assert len(splits) == SMALL_HPARAMS["cv_n_splits"]
    assert trained_model.training_history["grouped_cv"] == summary


def test_grouped_cv_can_be_skipped():
    model = ScalingPredictor(model_hyperparameters={**SMALL_HPARAMS, "cv_n_splits": 0})
    model.train(_loader())
    assert model.grouped_cv_summary is None
    assert model.is_trained


@pytest.mark.parametrize("name", ["LinearRegression", "SVR", "RandomForest"])
def test_alternative_notebook_models_train_end_to_end(name):
    model = ScalingPredictor(
        model_hyperparameters={
            **SMALL_HPARAMS,
            "model_name": name,
            "permutation_repeats": 2,
        }
    )
    model.train(_loader())
    preds = model.predict(_loader())
    assert np.all(np.isfinite(preds))
    assert len(model.selected_features) == N_STABLE


def test_training_selects_n_stable_candidate_features(trained_model):
    selected = trained_model.selected_features
    assert selected is not None
    assert len(selected) == N_STABLE
    assert len(set(selected)) == N_STABLE
    assert set(selected) <= set(ScalingPredictor.CANDIDATE_FEATURES)


def test_stability_scores_cover_every_candidate(trained_model):
    scores = trained_model.feature_stability_scores
    assert list(scores) == ScalingPredictor.CANDIDATE_FEATURES
    assert all(np.isfinite(v) for v in scores.values())


def test_selected_features_are_the_most_stable(trained_model):
    scores = trained_model.feature_stability_scores
    selected = trained_model.selected_features
    ranked = sorted(scores, key=scores.get, reverse=True)
    assert [scores[f] for f in selected] == [scores[f] for f in ranked[:N_STABLE]]


def test_feature_stability_table_is_the_notebook_dataframe(trained_model):
    table = trained_model.feature_stability_table
    assert list(table.columns) == [
        "feature",
        "mean_importance",
        "std_importance",
        "stability_score",
    ]
    assert len(table) == len(ScalingPredictor.CANDIDATE_FEATURES)
    assert table["stability_score"].is_monotonic_decreasing
    assert table["feature"].head(N_STABLE).tolist() == trained_model.selected_features


def test_predict_on_fixture(trained_model):
    preds = np.asarray(trained_model.predict(_loader())).ravel()
    assert preds.shape == (len(_dataset()),)
    assert np.all(np.isfinite(preds))


def test_feature_importance_sized_to_selected_features(trained_model):
    importance = trained_model.get_feature_importance()
    assert importance is not None
    assert len(importance) == N_STABLE


def test_predict_uses_only_selected_columns(trained_model):
    x = np.stack([_dataset()[0][0]])
    selected_idx = set(
        trained_model.estimator.named_steps["bootstrap_selector"].selected_idx_
    )
    unused = next(i for i in range(x.shape[1]) if i not in selected_idx)
    x_changed = x.copy()
    x_changed[0, unused] += 1e6
    np.testing.assert_array_equal(
        trained_model.estimator.predict(x), trained_model.estimator.predict(x_changed)
    )


def test_mlflow_extras_are_json_serialisable(trained_model):
    extras = trained_model.mlflow_extras()
    assert extras["params"]["selected_features"] == ", ".join(
        trained_model.selected_features
    )
    assert set(extras["metrics"]) == {
        f"cv_{m}_{s}" for m in ("mae", "rmse", "r2") for s in ("mean", "std")
    }
    assert set(extras["dicts"]) == {"feature_stability.json", "grouped_cv.json"}
    json.dumps(extras["dicts"])


def test_training_is_deterministic():
    runs = []
    for _ in range(2):
        model = ScalingPredictor(model_hyperparameters=SMALL_HPARAMS)
        model.train(_loader())
        runs.append(
            (
                model.selected_features,
                model.predict(_loader()),
                model.grouped_cv_summary,
            )
        )
    assert runs[0][0] == runs[1][0]
    np.testing.assert_array_equal(runs[0][1], runs[1][1])
    assert runs[0][2] == runs[1][2]


def test_save_load_roundtrip_preserves_predictions(trained_model, tmp_path):
    path = tmp_path / "scaling_predictor"
    assert trained_model.save(path)

    restored = ScalingPredictor.load(path)
    assert restored.is_trained
    assert restored.selected_features == trained_model.selected_features
    assert restored.grouped_cv_summary == trained_model.grouped_cv_summary
    np.testing.assert_array_equal(
        restored.predict(_loader()),
        trained_model.predict(_loader()),
    )


def test_legacy_pickled_estimator_still_predicts(trained_model):
    X_tr, y_tr = _xy()
    X_te, _ = _xy()
    legacy = BootstrapFeatureSelectingXGBRegressor.__new__(
        BootstrapFeatureSelectingXGBRegressor
    )
    legacy.__dict__.update(
        selected_idx_=[0, 1, 2],
        estimator_=XGBRegressor(n_estimators=5).fit(X_tr[:, [0, 1, 2]], y_tr),
        prediction_floor=0.01,
    )
    expected = np.maximum(legacy.estimator_.predict(X_te[:, [0, 1, 2]]), 0.01)
    np.testing.assert_array_equal(legacy.predict(X_te), expected)
    with pytest.raises(NotImplementedError):
        legacy.fit(X_tr, y_tr)

    model = ScalingPredictor()
    model.estimator = legacy
    assert model.selected_features == ScalingPredictor.CANDIDATE_FEATURES[:3]


def test_dataset_exposes_benchmark_groups():
    ds = _dataset()
    groups = ds.get_groups()
    assert len(groups) == len(ds)
    assert "Benchmark" not in ds.input_features
    np.testing.assert_array_equal(
        groups, pd.read_parquet(FIXTURE).loc[ds._df.index, "Benchmark"].to_numpy()
    )


def test_exclude_superlinear_matches_notebook_is_superlinear():
    df = pd.read_parquet(FIXTURE)

    def is_superlinear(row, pc_a, time_a):
        pc_b, time_b = row["Target_PC"], row["Time_Z"]
        if pc_b > pc_a:
            speedup, ideal = time_a / time_b, pc_b / pc_a
        else:
            speedup, ideal = time_b / time_a, pc_a / pc_b
        return speedup > ideal

    keep = ~df.apply(
        lambda r: is_superlinear(r, r["PC_X"], r["Time_X"]), axis=1
    ) & ~df.apply(lambda r: is_superlinear(r, r["PC_Y"], r["Time_Y"]), axis=1)
    ds = _dataset(exclude_superlinear=True)
    assert list(ds._df.index) == list(df.index[keep])
    assert len(_dataset()) == len(df)
