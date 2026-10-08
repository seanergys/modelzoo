import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, ClassVar, Dict, List, Literal, Optional, Tuple, Type, Union

import joblib
import numpy as np
import pandas as pd
from pydantic import Field, model_validator
from sklearn.base import BaseEstimator, RegressorMixin, TransformerMixin, clone
from sklearn.ensemble import RandomForestRegressor
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import Pipeline
from sklearn.svm import SVR
from sklearn.utils import resample
from xgboost import XGBRegressor

from seanergys_modelzoo.dataloader.seanergys_dataloader import SeanergysDataloader
from seanergys_modelzoo.datasets.common.seanergys_dataset import SeanergysDataset
from seanergys_modelzoo.datasets.scaling import ScalingDataset
from seanergys_modelzoo.models.common.seanergys_configurator import (
    SeanergysDataloaderParams,
    SeanergysDatasetParams,
)
from seanergys_modelzoo.models.common.seanergys_model import (
    SeanergysModel,
    SeanergysModelTask,
)
from seanergys_modelzoo.models.common.seanergys_model_metadata import (
    SeanergysModelMetadata,
)
from seanergys_modelzoo.models.common.sklearn_seanergys_model import (
    SeanergysSklearnModel,
)


SUPPORTED_REGRESSORS: Tuple[str, ...] = ("XGBoost", "RandomForest", "LinearRegression", "SVR")


def build_regressor(
    model_name: str = "XGBoost",
    n_estimators: int = 300,
    random_state: int = 42,
    n_jobs: Optional[int] = None,
) -> BaseEstimator:
    if model_name == "XGBoost":
        return XGBRegressor(n_estimators=n_estimators, random_state=random_state, n_jobs=n_jobs)
    if model_name == "RandomForest":
        return RandomForestRegressor(
            n_estimators=n_estimators, random_state=random_state, n_jobs=n_jobs
        )
    if model_name == "LinearRegression":
        return LinearRegression()
    if model_name == "SVR":
        return SVR(kernel="rbf")
    raise ValueError(f"Unknown model_name {model_name!r}. Valid: {list(SUPPORTED_REGRESSORS)}")


def get_feature_importance(
    model: BaseEstimator,
    X: np.ndarray,
    y: np.ndarray,
    model_name: str,
    permutation_repeats: int = 10,
) -> np.ndarray:
    if model_name in ("XGBoost", "RandomForest"):
        return model.feature_importances_
    if model_name == "LinearRegression":
        return np.abs(model.coef_)
    permutation = permutation_importance(
        model,
        X,
        y,
        n_repeats=permutation_repeats,
        random_state=42,
        scoring="neg_mean_squared_error",
    )
    return permutation.importances_mean


def evaluate_grouped_repeated(
    model: BaseEstimator,
    X: np.ndarray,
    y: np.ndarray,
    groups: np.ndarray,
    n_splits: int = 50,
    test_size: float = 0.2,
) -> Tuple[pd.DataFrame, Dict[str, float]]:
    splitter = GroupShuffleSplit(n_splits=n_splits, test_size=test_size, random_state=42)
    rows = []
    for split_id, (train_idx, test_idx) in enumerate(splitter.split(X, y, groups=groups)):
        fold_model = clone(model)
        fold_model.fit(X[train_idx], y[train_idx])
        predictions = fold_model.predict(X[test_idx])
        rows.append(
            {
                "split": split_id,
                "test_benchmarks": sorted(pd.unique(groups[test_idx]).tolist()),
                "MAE": mean_absolute_error(y[test_idx], predictions),
                "RMSE": np.sqrt(mean_squared_error(y[test_idx], predictions)),
                "R2": r2_score(y[test_idx], predictions),
            }
        )
    results = pd.DataFrame(rows)
    stats = results[["MAE", "RMSE", "R2"]].agg(["mean", "std"])
    summary = {
        f"{metric}_{stat}": float(stats.loc[stat, metric])
        for metric in ("MAE", "RMSE", "R2")
        for stat in ("mean", "std")
    }
    return results, summary


class BootstrapFeatureSelector(BaseEstimator, TransformerMixin):
    def __init__(
        self,
        model_name: str = "XGBoost",
        n_estimators: int = 300,
        random_state: int = 42,
        n_jobs: Optional[int] = None,
        n_bootstrap: int = 100,
        n_stable_features: int = 20,
        epsilon: float = 1e-8,
        permutation_repeats: int = 10,
    ):
        self.model_name = model_name
        self.n_estimators = n_estimators
        self.random_state = random_state
        self.n_jobs = n_jobs
        self.n_bootstrap = n_bootstrap
        self.n_stable_features = n_stable_features
        self.epsilon = epsilon
        self.permutation_repeats = permutation_repeats

    def fit(self, X: np.ndarray, y: np.ndarray) -> "BootstrapFeatureSelector":
        X = np.asarray(X, dtype=np.float64)
        y = np.asarray(y, dtype=np.float64).ravel()
        base_model = build_regressor(
            self.model_name, self.n_estimators, self.random_state, self.n_jobs
        )
        rng = np.random.RandomState(self.random_state)

        importance_storage = np.empty((self.n_bootstrap, X.shape[1]))
        for k in range(self.n_bootstrap):
            X_boot, y_boot = resample(X, y, replace=True, random_state=rng.randint(0, 100000))
            current_model = clone(base_model)
            current_model.fit(X_boot, y_boot)
            importance_storage[k] = get_feature_importance(
                current_model, X_boot, y_boot, self.model_name, self.permutation_repeats
            )

        self.mean_importance_ = importance_storage.mean(axis=0)
        self.std_importance_ = importance_storage.std(axis=0)
        self.feature_stability_ = self.mean_importance_ / (self.std_importance_ + self.epsilon)

        n_select = min(self.n_stable_features, X.shape[1])
        self.selected_idx_ = np.argsort(self.feature_stability_)[::-1][:n_select].tolist()
        print(f"Selected {n_select} features:")
        for rank, idx in enumerate(self.selected_idx_, 1):
            print(f"{rank:2d}. {ScalingPredictor.CANDIDATE_FEATURES[idx]}")
        self.n_features_in_ = X.shape[1]
        return self

    def transform(self, X: np.ndarray) -> np.ndarray:
        X = np.asarray(X, dtype=np.float64)
        return X[:, self.selected_idx_]


class BootstrapFeatureSelectingXGBRegressor(BaseEstimator, RegressorMixin):
    def fit(self, X: np.ndarray, y: np.ndarray) -> "BootstrapFeatureSelectingXGBRegressor":
        raise NotImplementedError(
            "BootstrapFeatureSelectingXGBRegressor is predict-only; train with ScalingPredictor."
        )

    def predict(self, X: np.ndarray) -> np.ndarray:
        X = np.asarray(X, dtype=np.float64)
        predictions = self.estimator_.predict(X[:, self.selected_idx_])
        floor = getattr(self, "prediction_floor", None)
        if floor is not None:
            predictions = np.maximum(predictions, floor)
        return predictions

    @property
    def feature_importances_(self) -> np.ndarray:
        return self.estimator_.feature_importances_


class ScalingPredictor(SeanergysSklearnModel):
    CANDIDATE_FEATURES: ClassVar[List[str]] = [
        "PC_X",
        "PC_Y",
        "Target_PC",
        "FLOPs_X",
        "MEM BW_X",
        "MPI %_X",
        "Irecv_pct_X",
        "Wait_pct_X",
        "Commdup_pct_X",
        "Allreduce_pct_X",
        "Waitall_pct_X",
        "Isend_pct_X",
        "Bcast_pct_X",
        "Reduce_pct_X",
        "Barrier_pct_X",
        "Send_pct_X",
        "Alltoall_pct_X",
        "Comm_split_pct_X",
        "Comm_free_pct_X",
        "Alltoallv_pct_X",
        "Recv_pct_X",
        "Dimscreate_pct_X",
        "Allgather_pct_X",
        "Scan_pct_X",
        "Gather_pct_X",
        "Type_free_pct_X",
        "Type_commit_pct_X",
        "Sendrecv_pct_X",
        "Test_pct_X",
        "Testany_pct_X",
        "Waitany_pct_X",
        "Cancel_pct_X",
        "Iprobe_pct_X",
        "Scatterv_pct_X",
        "Scatter_pct_X",
        "Gatherv_pct_X",
        "WIn_lock_pct_X",
        "WIn_flush_pct_X",
        "Put_pct_X",
        "Group_incl_pct_X",
        "Get_pct_X",
        "Win_unlock_pct_X",
        "Win_free_pct_X",
        "Comm_group_pct_X",
        "Win_allocate_pct_X",
        "Comm_create_pct_X",
        "Probe_pct_X",
        "Allgatherv_pct_X",
        "Buffer_attach_pct_X",
        "Buffer_detach_pct_X",
        "Cart_create_pct_X",
        "Cart_get_pct_X",
        "Start_pct_X",
        "Ibarrier_pct_X",
        "Issend_pct_X",
        "Testall_pct_X",
        "File_open_pct_X",
        "File_set_size_pct_X",
        "File_close_pct_X",
        "Allreduce_msg_X",
        "Isend_msg_X",
        "Bcast_msg_X",
        "Reduce_msg_X",
        "Send_msg_X",
        "Alltoall_msg_X",
        "Scan_msg_X",
        "Allgather_msg_X",
        "Gather_msg_X",
        "Sendrecv_msg_X",
        "Scatter_msg_X",
        "Gatherv_msg_X",
        "Allgatherv_msg_X",
        "Issend_msg_X",
        "Communication_Time_X",
        "Computation_Time_X",
        "Ecomp_X",
        "Time_X",
        "FLOPs_Y",
        "MEM BW_Y",
        "MPI %_Y",
        "Irecv_pct_Y",
        "Wait_pct_Y",
        "Commdup_pct_Y",
        "Allreduce_pct_Y",
        "Waitall_pct_Y",
        "Isend_pct_Y",
        "Bcast_pct_Y",
        "Reduce_pct_Y",
        "Barrier_pct_Y",
        "Send_pct_Y",
        "Alltoall_pct_Y",
        "Comm_split_pct_Y",
        "Comm_free_pct_Y",
        "Alltoallv_pct_Y",
        "Recv_pct_Y",
        "Dimscreate_pct_Y",
        "Allgather_pct_Y",
        "Scan_pct_Y",
        "Gather_pct_Y",
        "Type_free_pct_Y",
        "Type_commit_pct_Y",
        "Sendrecv_pct_Y",
        "Test_pct_Y",
        "Testany_pct_Y",
        "Waitany_pct_Y",
        "Cancel_pct_Y",
        "Iprobe_pct_Y",
        "Scatterv_pct_Y",
        "Scatter_pct_Y",
        "Gatherv_pct_Y",
        "WIn_lock_pct_Y",
        "WIn_flush_pct_Y",
        "Put_pct_Y",
        "Group_incl_pct_Y",
        "Get_pct_Y",
        "Win_unlock_pct_Y",
        "Win_free_pct_Y",
        "Comm_group_pct_Y",
        "Win_allocate_pct_Y",
        "Comm_create_pct_Y",
        "Probe_pct_Y",
        "Allgatherv_pct_Y",
        "Buffer_attach_pct_Y",
        "Buffer_detach_pct_Y",
        "Cart_create_pct_Y",
        "Cart_get_pct_Y",
        "Start_pct_Y",
        "Ibarrier_pct_Y",
        "Issend_pct_Y",
        "Testall_pct_Y",
        "File_open_pct_Y",
        "File_set_size_pct_Y",
        "File_close_pct_Y",
        "Allreduce_msg_Y",
        "Isend_msg_Y",
        "Bcast_msg_Y",
        "Reduce_msg_Y",
        "Send_msg_Y",
        "Alltoall_msg_Y",
        "Scan_msg_Y",
        "Allgather_msg_Y",
        "Gather_msg_Y",
        "Sendrecv_msg_Y",
        "Scatter_msg_Y",
        "Gatherv_msg_Y",
        "Allgatherv_msg_Y",
        "Issend_msg_Y",
        "Communication_Time_Y",
        "Computation_Time_Y",
        "Ecomp_Y",
        "Time_Y",
        "MPI %_Trend",
        "FLOPs_Trend",
        "MEM BW_Trend",
    ]

    DEFAULT_HYPERPARAMETERS: ClassVar[Dict[str, Any]] = {
        "model_name": "XGBoost",
        "n_estimators": 300,
        "random_state": 42,
        "n_jobs": None,
        "n_bootstrap": 100,
        "n_stable_features": 20,
        "epsilon": 1e-8,
        "permutation_repeats": 10,
        "cv_n_splits": 50,
        "cv_test_size": 0.2,
    }
    _SELECTOR_KEYS: ClassVar[Tuple[str, ...]] = (
        "model_name",
        "n_estimators",
        "random_state",
        "n_jobs",
        "n_bootstrap",
        "n_stable_features",
        "epsilon",
        "permutation_repeats",
    )

    @model_validator(mode="before")
    @classmethod
    def _inject_defaults(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        values.setdefault("model_class", Pipeline)
        values.setdefault("task_type", SeanergysModelTask.REGRESSION)
        values.setdefault("supported_datasets", [ScalingDataset])
        values.setdefault(
            "metadata",
            SeanergysModelMetadata(name="ScalingPredictor"),
        )
        return values

    feature_selection_scope: Literal["all", "train"] = Field(
        default="all",
        description=(
            "Rows the bootstrap stability step runs on: 'all' = the unfiltered "
            "dataset (the notebook's behaviour), 'train' = the training split only."
        ),
    )

    @property
    def hyperparameters(self) -> Dict[str, Any]:
        return {**self.DEFAULT_HYPERPARAMETERS, **self.model_hyperparameters}

    def build_model(self) -> None:
        unknown = set(self.model_hyperparameters) - set(self.DEFAULT_HYPERPARAMETERS)
        if unknown:
            raise ValueError(
                f"Unknown ScalingPredictor hyperparameters {sorted(unknown)}. "
                f"Valid: {sorted(self.DEFAULT_HYPERPARAMETERS)}"
            )
        hp = self.hyperparameters
        self.estimator = Pipeline(
            [
                (
                    "bootstrap_selector",
                    BootstrapFeatureSelector(**{k: hp[k] for k in self._SELECTOR_KEYS}),
                ),
                (
                    "regressor",
                    build_regressor(
                        hp["model_name"], hp["n_estimators"], hp["random_state"], hp["n_jobs"]
                    ),
                ),
            ]
        )
        self.logger.info(f"Built {self.model_name} with {hp['model_name']} pipeline")

    def train(
        self,
        train_data_loader: SeanergysDataloader,
        val_data_loader: Optional[SeanergysDataloader] = None,
        training_loss: Optional[Callable] = None,
        validation_metrics: Optional[List[Callable]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        self.logger.info(f"Starting training {self.model_name}")
        start_time = time.time()
        hp = self.hyperparameters
        selector: BootstrapFeatureSelector = self.estimator.named_steps["bootstrap_selector"]
        regressor = self.estimator.named_steps["regressor"]

        X_train, y_train = self._extract_data_from_loader(train_data_loader)
        y_train = y_train.ravel()

        selection_dataset = train_data_loader.dataset
        if self.feature_selection_scope == "all":
            selection_dataset = self._unfiltered_dataset(selection_dataset)
        if selection_dataset is train_data_loader.dataset:
            X_select, y_select = X_train, y_train
        else:
            X_select, y_select = self._extract_data_from_loader(
                SeanergysDataloader(dataset=selection_dataset, batch_size=train_data_loader.batch_size)
            )
            y_select = y_select.ravel()

        self.logger.info(
            f"STEP 1: bootstrap feature stability ({hp['n_bootstrap']} x "
            f"{hp['model_name']}) on {len(X_select)} rows"
        )
        selector.fit(X_select, y_select)
        self.logger.info(f"Selected features: {self.selected_features}")

        groups = (
            selection_dataset.get_groups() if hasattr(selection_dataset, "get_groups") else None
        )
        self.estimator.grouped_cv_ = None
        if hp["cv_n_splits"] and groups is not None and len(np.unique(groups)) >= 2:
            self.logger.info(
                f"STEP 2: grouped repeated evaluation ({hp['cv_n_splits']} splits, "
                f"test_size={hp['cv_test_size']})"
            )
            results, summary = evaluate_grouped_repeated(
                regressor,
                selector.transform(X_select),
                y_select,
                np.asarray(groups),
                n_splits=hp["cv_n_splits"],
                test_size=hp["cv_test_size"],
            )
            self.estimator.grouped_cv_ = {
                "summary": summary,
                "splits": results.to_dict(orient="records"),
            }
            self.logger.info(f"Grouped evaluation summary: {summary}")
        else:
            self.logger.info("STEP 2 skipped (cv_n_splits=0 or fewer than 2 groups)")

        X_train_reduced = selector.transform(X_train)
        self.logger.info(
            f"Training {hp['model_name']} on {X_train_reduced.shape[0]} rows x "
            f"{X_train_reduced.shape[1]} selected features"
        )
        regressor.fit(X_train_reduced, y_train, **kwargs)

        train_loss_value = None
        if training_loss:
            train_loss_value = training_loss(y_train, self.estimator.predict(X_train))

        self.is_trained = True
        training_time = time.time() - start_time
        assert self.metadata is not None
        self.metadata.set_field("last_trained", datetime.now().isoformat())
        self.metadata.set_field("training_time", training_time)
        if train_loss_value is not None:
            self.metadata.set_field("training_loss", train_loss_value)
        self.logger.info(f"Training completed in {training_time:.2f}s")

        val_metrics_values = None
        val_time = None
        if val_data_loader is not None and validation_metrics:
            t0_val = time.time()
            X_val, y_val = self._extract_data_from_loader(val_data_loader)
            val_preds = self.estimator.predict(X_val)
            val_metrics_values = {m.__name__: m(y_val, val_preds) for m in validation_metrics}
            val_time = time.time() - t0_val
            self.metadata.set_field("validation_metrics", val_metrics_values)
            self.metadata.set_field("validation_time", val_time)

        self.training_history = {
            "training": {"training_loss": train_loss_value, "training_time": training_time},
            "validation": {"validation_metrics": val_metrics_values, "validation_time": val_time},
            "grouped_cv": self.grouped_cv_summary,
        }
        return self.training_history

    def _unfiltered_dataset(self, dataset: SeanergysDataset) -> SeanergysDataset:
        if not getattr(dataset, "filters", None):
            return dataset
        full = dataset.model_copy(update={"filters": None, "stats": {}})
        full.load_data()
        return full

    def _selector(self) -> Optional[Any]:
        steps = getattr(self.estimator, "named_steps", None)
        return steps["bootstrap_selector"] if steps else self.estimator

    @property
    def selected_features(self) -> Optional[List[str]]:
        idx = getattr(self._selector(), "selected_idx_", None)
        if idx is None:
            return None
        return [self.CANDIDATE_FEATURES[i] for i in idx]

    @property
    def feature_stability_scores(self) -> Optional[Dict[str, float]]:
        scores = getattr(self._selector(), "feature_stability_", None)
        if scores is None:
            return None
        return dict(zip(self.CANDIDATE_FEATURES, (float(s) for s in scores)))

    @property
    def feature_stability_table(self) -> Optional[pd.DataFrame]:
        selector = self._selector()
        if getattr(selector, "mean_importance_", None) is None:
            return None
        return pd.DataFrame(
            {
                "feature": self.CANDIDATE_FEATURES,
                "mean_importance": selector.mean_importance_,
                "std_importance": selector.std_importance_,
                "stability_score": selector.feature_stability_,
            }
        ).sort_values(by="stability_score", ascending=False)

    @property
    def grouped_cv_summary(self) -> Optional[Dict[str, float]]:
        cv = getattr(self.estimator, "grouped_cv_", None)
        return cv["summary"] if cv else None

    def get_feature_importance(self) -> Optional[np.ndarray]:
        steps = getattr(self.estimator, "named_steps", None)
        regressor = steps["regressor"] if steps else self.estimator
        if hasattr(regressor, "feature_importances_"):
            return regressor.feature_importances_
        if hasattr(regressor, "coef_"):
            return np.abs(regressor.coef_)
        return None

    def mlflow_extras(self) -> Dict[str, Any]:
        extras: Dict[str, Any] = {"params": {}, "metrics": {}, "dicts": {}}
        if self.selected_features is not None:
            extras["params"]["selected_features"] = ", ".join(self.selected_features)
        table = self.feature_stability_table
        if table is not None:
            extras["dicts"]["feature_stability.json"] = table.to_dict(orient="records")
        cv = getattr(self.estimator, "grouped_cv_", None)
        if cv:
            extras["metrics"] = {f"cv_{k.lower()}": v for k, v in cv["summary"].items()}
            extras["dicts"]["grouped_cv.json"] = cv
        return extras

    def save(
        self, path: Union[str, Path] = "./saved_model", compress: int = 3, **kwargs
    ) -> bool:
        """
        Persist the model in the layout SeanergysSklearnModel.load() reads.

        Overridden because the estimator is a Pipeline: the inherited save()
        dumps Pipeline.get_params(), which holds the step objects themselves
        (BootstrapFeatureSelector, the regressor), and json cannot serialise
        them. Here each step is recorded as its class path plus its own
        get_params(deep=False), which are plain values. load() does not read
        sklearn_params back; the fitted Pipeline comes from the joblib file.
        """
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)
        estimator_path = path / self.model_name / ".joblib"
        estimator_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            joblib.dump(self.estimator, str(estimator_path), compress=compress)
            self.logger.info(f"Estimator saved to {path}")

            self._save_metadata(path)

            info = {
                "model_class_module": self.model_class.__module__,
                "model_class_name": self.model_class.__name__,
                "task_type": self.task_type.name,
                "model_hyperparameters": self.model_hyperparameters,
                "sklearn_params": {
                    name: {
                        "class": f"{type(step).__module__}.{type(step).__name__}",
                        "params": step.get_params(deep=False),
                    }
                    for name, step in self.estimator.steps
                },
            }
            info_path = path.parent / f"{path.stem}_info.json"
            with open(info_path, "w") as f:
                json.dump(info, f, indent=2)
            self.logger.info(f"Model info saved to {info_path}")

            return True

        except Exception as e:
            self.logger.error(f"Error saving model: {e}")
            return False

    @classmethod
    def get_train_config(
        cls, dataset_name: str = "scaling", get_dummy_data: bool = False
    ) -> Dict[
        str,
        Tuple[
            "ScalingPredictor",
            Type[SeanergysDataset],
            Tuple[SeanergysDatasetParams, SeanergysDataloaderParams],
        ],
    ]:
        if dataset_name != "scaling":
            raise Exception("Invalid dataset name. Datasets allowed: 'scaling'")

        model_scaling = cls(  # type: ignore[call-arg]
            model_hyperparameters=dict(cls.DEFAULT_HYPERPARAMETERS)
        )
        model_scaling.logger.info("Training on the scaling dataset")

        ds_params = SeanergysDatasetParams(
            use_zenodo_url=True,
            is_dummy=get_dummy_data,
            input_features=list(cls.CANDIDATE_FEATURES),
            output_features=["Speedup_XZ"],
        )
        return {
            "scaling": (
                model_scaling,
                ScalingDataset,
                (ds_params, SeanergysDataloaderParams(batch_size=1)),
            )
        }

    @classmethod
    def get_test_config(
        cls,
        model: SeanergysModel,
        dataset_name: str = "scaling",
        get_dummy_data: bool = False,
    ) -> Dict[str, Tuple["ScalingPredictor", SeanergysDataloader]]:
        assert isinstance(model, ScalingPredictor)
        if dataset_name != "scaling":
            raise Exception("Invalid dataset name. Datasets allowed: 'scaling'")

        model.logger.info("Testing on the scaling dataset")
        scaling = ScalingDataset(
            use_zenodo_url=True,
            is_dummy=get_dummy_data,
            input_features=list(cls.CANDIDATE_FEATURES),
            output_features=["Speedup_XZ"],
        )
        return {"scaling": (model, SeanergysDataloader(dataset=scaling, batch_size=1))}