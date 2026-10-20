import itertools
import json
import time
from datetime import datetime
from pathlib import Path
from typing import (
    Any,
    Callable,
    ClassVar,
    Dict,
    List,
    Optional,
    Sequence,
    Tuple,
    Type,
    Union,
)

import joblib
import numpy as np
from pydantic import model_validator
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import cross_val_score
from sklearn.neighbors import KNeighborsRegressor
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVR
from xgboost import XGBRegressor

from seanergys_modelzoo.dataloader.seanergys_dataloader import SeanergysDataloader
from seanergys_modelzoo.datasets.colocation import ColocationDataset
from seanergys_modelzoo.datasets.common.seanergys_dataset import SeanergysDataset
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

max_features_options = ["sqrt", "log2", 0.2, 0.5, 0.7]
min_samples_split_options = [2, 4, 6, 8]
bootstrap_options = [True, False]
n_estimators_options = [9, 13, 18, 22]

hidden_layer_sizes_options = [(10,), (50,), (100,), (100, 50), (100, 100, 50)]
alpha_options = [0.0001, 0.001, 0.01, 0.1]
activation_options = ["identity", "logistic", "tanh", "relu"]
learning_rate_options = ["constant", "invscaling", "adaptive"]
learning_rate_init_options = [0.001, 0.01, 0.1]
mlp_tol_options = [1e-4, 1e-3, 1e-2]

kernel_options = ["linear", "rbf", "poly"]
C_options = [0.1, 1, 10, 100]
svm_tol_options = [1e-3, 1e-2]
coef0_options = [0.0, 0.5]
degree_options = [2, 3]
gamma_options = ["scale", 0.01, 1]
epsilon_options = [0.01, 0.1]

ridge_alpha_options = [0.0001, 0.001, 0.01, 0.1, 1, 10, 100]
ridge_fit_intercept_options = [True, False]
ridge_solver_options = ["auto", "svd", "cholesky", "lsqr"]

n_neighbors_options = [3, 5, 7, 9]
weights_options = ["uniform", "distance"]
algorithm_options = ["auto", "ball_tree", "kd_tree", "brute"]
leaf_size_options = [20, 30, 40, 50]
p_options = [1, 2]
metric_options = ["minkowski", "euclidean", "manhattan"]

learning_rate_gbm_options = [0.1, 0.05, 0.01, 0.2]
max_depth_options = [3, 5, 7, 10]

xgb_n_estimators_options = [50, 100, 200, 300]
xgb_max_depth_options = [3, 5, 7]
xgb_learning_rate_options = [0.01, 0.05, 0.1]
xgb_subsample_options = [0.8, 1.0]
xgb_colsample_bytree_options = [0.8, 1.0]


def build_combinations(
    rf_n_estimators: Sequence[int] = tuple(n_estimators_options),
    xgb_n_estimators: Sequence[int] = tuple(xgb_n_estimators_options),
) -> Dict[str, List[Dict[str, Any]]]:
    
    rf_combinations = [
        {
            "max_features": mf,
            "min_samples_split": mss,
            "bootstrap": bootstrap,
            "n_estimators": n,
        }
        for mf, mss, bootstrap, n in itertools.product(
            max_features_options,
            min_samples_split_options,
            bootstrap_options,
            rf_n_estimators,
        )
    ]

    mlp_combinations = [
        {
            "hidden_layer_sizes": hls,
            "alpha": alpha,
            "activation": activation,
            "learning_rate": lr,
            "learning_rate_init": lri,
            "tol": tol,
        }
        for hls, alpha, activation, lr, lri, tol in itertools.product(
            hidden_layer_sizes_options,
            alpha_options,
            activation_options,
            learning_rate_options,
            learning_rate_init_options,
            mlp_tol_options,
        )
    ]

    svm_combinations = []
    for kernel, C, tol, gamma, epsilon in itertools.product(
        kernel_options,
        C_options,
        svm_tol_options,
        gamma_options,
        epsilon_options,
    ):
        degrees = degree_options if kernel == "poly" else [3]
        coef0_values = coef0_options if kernel in ["poly", "sigmoid"] else [0.0]
        for degree, coef0 in itertools.product(degrees, coef0_values):
            svm_combinations.append(
                {
                    "kernel": kernel,
                    "C": C,
                    "tol": tol,
                    "gamma": gamma,
                    "epsilon": epsilon,
                    "degree": degree,
                    "coef0": coef0,
                }
            )

    ridge_combinations = [
        {"alpha": alpha, "fit_intercept": fit_intercept, "solver": solver}
        for alpha, fit_intercept, solver in itertools.product(
            ridge_alpha_options,
            ridge_fit_intercept_options,
            ridge_solver_options,
        )
    ]

    knn_combinations = [
        {
            "n_neighbors": n,
            "weights": weights,
            "algorithm": algorithm,
            "leaf_size": leaf_size,
            "p": p,
            "metric": metric,
        }
        for n, weights, algorithm, leaf_size, p, metric in itertools.product(
            n_neighbors_options,
            weights_options,
            algorithm_options,
            leaf_size_options,
            p_options,
            metric_options,
        )
    ]

    gbm_combinations = [
        {
            "max_features": mf,
            "min_samples_split": mss,
            "n_estimators": n,
            "learning_rate": lr,
            "max_depth": depth,
        }
        for mf, mss, n, lr, depth in itertools.product(
            max_features_options,
            min_samples_split_options,
            rf_n_estimators,
            learning_rate_gbm_options,
            max_depth_options,
        )
    ]

    xgb_combinations = [
        {
            "n_estimators": n,
            "max_depth": depth,
            "learning_rate": lr,
            "subsample": subsample,
            "colsample_bytree": colsample,
        }
        for n, depth, lr, subsample, colsample in itertools.product(
            xgb_n_estimators,
            xgb_max_depth_options,
            xgb_learning_rate_options,
            xgb_subsample_options,
            xgb_colsample_bytree_options,
        )
    ]

    return {
        "Random Forests": rf_combinations,
        "Multi-Layer Perceptron": mlp_combinations,
        "Support Vector Machine": svm_combinations,
        "Ridge Regression": ridge_combinations,
        "K-Nearest Neighbors": knn_combinations,
        "Gradient Boosting Machine": gbm_combinations,
        "XGBoost": xgb_combinations,
    }


MODEL_CLASSES: Dict[str, type] = {
    "Random Forests": RandomForestRegressor,
    "Multi-Layer Perceptron": MLPRegressor,
    "Support Vector Machine": SVR,
    "Ridge Regression": Ridge,
    "K-Nearest Neighbors": KNeighborsRegressor,
    "Gradient Boosting Machine": GradientBoostingRegressor,
    "XGBoost": XGBRegressor,
}

TECHNOLOGIES: List[str] = [
    "Random Forests",
    'Multi-Layer Perceptron',
    "Support Vector Machine",
    "Ridge Regression",
    "K-Nearest Neighbors",
    "Gradient Boosting Machine",
    "XGBoost",
]

SCALED_MODELS = {
    "Multi-Layer Perceptron",
    "Support Vector Machine",
    "Ridge Regression",
    "K-Nearest Neighbors",
}


def build_model(technology: str, model_params: Dict[str, Any]) -> Any:
    """Cell 6: the estimator, behind a StandardScaler for the scaled models."""
    model_class = MODEL_CLASSES[technology]
    if technology in SCALED_MODELS:
        return Pipeline(
            [
                ("scaler", StandardScaler()),
                ("model", model_class(**model_params)),
            ]
        )
    return model_class(**model_params)


def with_fixed_params(technology: str, config: Dict[str, Any]) -> Dict[str, Any]:
    model_params = config.copy()
    if technology in ["Random Forests", "Gradient Boosting Machine"]:
        model_params["random_state"] = 1
    elif technology == "Multi-Layer Perceptron":
        model_params["random_state"] = 1
        model_params["max_iter"] = 500
    elif technology == "XGBoost":
        model_params["random_state"] = 1
        model_params["objective"] = "reg:squarederror"
        model_params["eval_metric"] = "rmse"
        model_params["n_jobs"] = 1
    return model_params


def evaluate_technology(
    technology: str,
    combinations: List[Dict[str, Any]],
    train_X: np.ndarray,
    train_y: np.ndarray,
    val_X: Optional[np.ndarray] = None,
    val_y: Optional[np.ndarray] = None,
    cv: int = 5,
    n_jobs: Optional[int] = -1,
) -> Tuple[Any, Dict[str, Any]]:
    best_config = None
    best_cv_mae = float("inf")
    best_model_index = -1

    for i, config in enumerate(combinations):
        model = build_model(technology, with_fixed_params(technology, config))
        cv_scores = cross_val_score(
            model,
            train_X,
            train_y,
            cv=cv,
            scoring="neg_mean_absolute_error",
            n_jobs=n_jobs,
        )
        mean_cv_mae = -cv_scores.mean()
        if mean_cv_mae < best_cv_mae:
            best_cv_mae = mean_cv_mae
            best_config = config.copy()
            best_model_index = i

    assert best_config is not None

    best_model = build_model(technology, with_fixed_params(technology, best_config))
    start_train = time.perf_counter_ns()
    best_model.fit(train_X, train_y)
    end_train = time.perf_counter_ns()
    training_time = (end_train - start_train) / 1_000_000

    performance: Dict[str, Optional[float]] = {
        "CV_MAE": float(best_cv_mae),
        "MAE": None,
        "RMSE": None,
        "R2": None,
    }
    inference_time = None
    if val_X is not None and val_y is not None and len(val_X):
        start_inference = time.perf_counter_ns()
        val_preds = best_model.predict(val_X)
        end_inference = time.perf_counter_ns()
        inference_time = (end_inference - start_inference) / 1_000_000
        performance["MAE"] = float(mean_absolute_error(val_y, val_preds))
        performance["RMSE"] = float(np.sqrt(mean_squared_error(val_y, val_preds)))
        performance["R2"] = (
            float(r2_score(val_y, val_preds)) if len(val_y) > 1 else None
        )

    info = {
        "model_name": f"Model_{best_model_index}",
        "params": best_config,
        "performance": performance,
        "training_time": training_time,
        "inference_time": inference_time,
    }
    return best_model, info


def select_best_technology(all_models_info: Dict[str, Dict[str, Any]]) -> str:
    return min(
        all_models_info,
        key=lambda technology: all_models_info[technology]["performance"]["CV_MAE"],
    )


def results_table(all_models_info: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    results = [
        {
            "Model": technology,
            "Best Configuration": info["model_name"],
            "Best Parameters": info["params"],
            "CV MAE": info["performance"]["CV_MAE"],
            "Validation MAE": info["performance"]["MAE"],
            "Validation RMSE": info["performance"]["RMSE"],
            "Validation R²": info["performance"]["R2"],
            "Training Time (ms)": info["training_time"],
            "Inference Time (ms)": info["inference_time"],
        }
        for technology, info in all_models_info.items()
    ]
    return sorted(results, key=lambda row: row["CV MAE"])


class ColocationPredictor(SeanergysSklearnModel):

    FEATURES: ClassVar[List[str]] = [
        "FLOPS_A",
        "Memory_A",
        "LLC_Misses_A",
        "LLC_Hits_A",
        "MPI_time_A",
        "FLOPS_B",
        "Memory_B",
        "LLC_Misses_B",
        "LLC_Hits_B",
        "MPI_time_B",
    ]
    TARGET: ClassVar[str] = "SpeedupA"

    DEFAULT_HYPERPARAMETERS: ClassVar[Dict[str, Any]] = {
        "technologies": list(TECHNOLOGIES),
        "cv_folds": 5,
        "n_jobs": -1,
        "n_estimators": None,
    }

    @model_validator(mode="before")
    @classmethod
    def _inject_defaults(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        values.setdefault("model_class", Pipeline)
        values.setdefault("task_type", SeanergysModelTask.REGRESSION)
        values.setdefault("supported_datasets", [ColocationDataset])
        values.setdefault(
            "metadata", SeanergysModelMetadata(name="ColocationPredictor")
        )
        return values

    @property
    def hyperparameters(self) -> Dict[str, Any]:
        return {**self.DEFAULT_HYPERPARAMETERS, **self.model_hyperparameters}

    def build_model(self) -> None:
        unknown = set(self.model_hyperparameters) - set(self.DEFAULT_HYPERPARAMETERS)
        if unknown:
            raise ValueError(
                f"Unknown ColocationPredictor hyperparameters {sorted(unknown)}. "
                f"Valid: {sorted(self.DEFAULT_HYPERPARAMETERS)}"
            )
        invalid = set(self.hyperparameters["technologies"]) - set(MODEL_CLASSES)
        if invalid or not self.hyperparameters["technologies"]:
            raise ValueError(
                f"Invalid technologies {sorted(invalid)}. Supported: {list(MODEL_CLASSES)}"
            )
        self.estimator = DummyRegressor()
        self.logger.info(
            f"Built {self.model_name}; train() selects among {self.hyperparameters['technologies']}"
        )

    def model_specs(self) -> Dict[str, List[Dict[str, Any]]]:
        n_estimators = self.hyperparameters["n_estimators"]
        if n_estimators is None:
            return build_combinations()
        return build_combinations([n_estimators], [n_estimators])

    def _validation_data(
        self,
        train_data_loader: SeanergysDataloader,
        val_data_loader: Optional[SeanergysDataloader],
    ) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        if val_data_loader is None:
            dataset = train_data_loader.dataset
            if getattr(dataset, "split", None) != "train":
                return None, None
            hold_out = dataset.model_copy(update={"split": "test", "stats": {}})
            hold_out.load_data()
            if len(hold_out) == 0:
                return None, None
            val_data_loader = SeanergysDataloader(dataset=hold_out, batch_size=1)
        val_X, val_y = self._extract_data_from_loader(val_data_loader)
        return val_X, val_y.ravel()

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

        train_X, train_y = self._extract_data_from_loader(train_data_loader)
        train_y = train_y.ravel()
        val_X, val_y = self._validation_data(train_data_loader, val_data_loader)

        specs = self.model_specs()
        all_models_info: Dict[str, Dict[str, Any]] = {}
        fitted_models: Dict[str, Any] = {}
        for technology in hp["technologies"]:
            self.logger.info(f"Evaluating {technology}...")
            fitted_models[technology], all_models_info[technology] = (
                evaluate_technology(
                    technology,
                    specs[technology],
                    train_X,
                    train_y,
                    val_X,
                    val_y,
                    cv=hp["cv_folds"],
                    n_jobs=hp["n_jobs"],
                )
            )
            info = all_models_info[technology]
            self.logger.info(
                f"{technology}: {info['model_name']} {info['params']} "
                f"CV MAE {info['performance']['CV_MAE']:.6f}, "
                f"validation {info['performance']}"
            )

        best_technology = select_best_technology(all_models_info)
        self.estimator = fitted_models[best_technology]
        self.estimator.best_technology_ = best_technology
        self.estimator.best_model_info_ = all_models_info[best_technology]
        self.estimator.all_models_info_ = all_models_info
        best = all_models_info[best_technology]
        self.logger.info(
            f"Best model family: {best_technology}, configuration {best['model_name']}, "
            f"CV MAE {best['performance']['CV_MAE']:.6f}"
        )

        train_loss_value = None
        if training_loss:
            train_loss_value = training_loss(train_y, self.estimator.predict(train_X))

        self.is_trained = True
        training_time = time.time() - start_time
        assert self.metadata is not None
        self.metadata.set_field("last_trained", datetime.now().isoformat())
        self.metadata.set_field("training_time", training_time)
        if train_loss_value is not None:
            self.metadata.set_field("training_loss", train_loss_value)
        self.logger.info(f"Training completed in {training_time:.2f}s")

        val_metrics_values = None
        if val_X is not None and validation_metrics:
            val_preds = self.estimator.predict(val_X)
            val_metrics_values = {
                m.__name__: m(val_y, val_preds) for m in validation_metrics
            }
            self.metadata.set_field("validation_metrics", val_metrics_values)

        self.training_history = {
            "training": {
                "training_loss": train_loss_value,
                "training_time": training_time,
            },
            "validation": {"validation_metrics": val_metrics_values},
            "best_technology": best_technology,
            "results": results_table(all_models_info),
        }
        return self.training_history

    @property
    def best_technology(self) -> Optional[str]:
        return getattr(self.estimator, "best_technology_", None)

    @property
    def results(self) -> Optional[List[Dict[str, Any]]]:
        info = getattr(self.estimator, "all_models_info_", None)
        return results_table(info) if info else None

    def get_feature_importance(self) -> Optional[np.ndarray]:
        steps = getattr(self.estimator, "named_steps", None)
        estimator = steps["model"] if steps else self.estimator
        if hasattr(estimator, "feature_importances_"):
            return estimator.feature_importances_
        if hasattr(estimator, "coef_"):
            return np.abs(estimator.coef_)
        return None

    def mlflow_extras(self) -> Dict[str, Any]:
        extras: Dict[str, Any] = {"params": {}, "metrics": {}, "dicts": {}}
        best = getattr(self.estimator, "best_model_info_", None)
        if not self.is_trained or best is None:
            return extras
        extras["params"]["best_technology"] = self.best_technology
        extras["params"]["best_configuration"] = best["model_name"]
        extras["params"].update({f"best.{k}": v for k, v in best["params"].items()})
        extras["metrics"]["cv_mae"] = best["performance"]["CV_MAE"]
        extras["dicts"]["results.json"] = self.results
        importance = self.get_feature_importance()
        if importance is not None:
            extras["dicts"]["feature_importance.json"] = dict(
                zip(self.FEATURES, (float(v) for v in importance))
            )
        return extras

    def save(
        self, path: Union[str, Path] = "./saved_model", compress: int = 3, **kwargs
    ) -> bool:
        
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)
        estimator_path = path / self.model_name / ".joblib"
        estimator_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            joblib.dump(self.estimator, str(estimator_path), compress=compress)
            self.logger.info(f"Estimator saved to {path}")

            self._save_metadata(path)

            steps = getattr(self.estimator, "steps", [("model", self.estimator)])
            info = {
                "model_class_module": self.model_class.__module__,
                "model_class_name": self.model_class.__name__,
                "task_type": self.task_type.name,
                "model_hyperparameters": self.model_hyperparameters,
                "best_technology": self.best_technology,
                "sklearn_params": {
                    name: {
                        "class": f"{type(step).__module__}.{type(step).__name__}",
                        "params": step.get_params(deep=False),
                    }
                    for name, step in steps
                },
            }
            info_path = path.parent / f"{path.stem}_info.json"
            with open(info_path, "w") as f:
                json.dump(info, f, indent=2, default=str)
            self.logger.info(f"Model info saved to {info_path}")

            return True

        except Exception as e:
            self.logger.error(f"Error saving model: {e}")
            return False

    @classmethod
    def get_train_config(
        cls, dataset_name: str = "colocation", get_dummy_data: bool = False
    ) -> Dict[
        str,
        Tuple[
            "ColocationPredictor",
            Type[SeanergysDataset],
            Tuple[SeanergysDatasetParams, SeanergysDataloaderParams],
        ],
    ]:
        if dataset_name != "colocation":
            raise Exception("Invalid dataset name. Datasets allowed: 'colocation'")

        model = cls(model_hyperparameters=dict(cls.DEFAULT_HYPERPARAMETERS))  # type: ignore[call-arg]
        model.logger.info("Training on the colocation dataset")

        ds_params = SeanergysDatasetParams(
            use_zenodo_url=True,
            is_dummy=get_dummy_data,
            split="train",
            input_features=list(cls.FEATURES),
            output_features=[cls.TARGET],
        )
        return {
            "colocation": (
                model,
                ColocationDataset,
                (ds_params, SeanergysDataloaderParams(batch_size=1)),
            )
        }

    @classmethod
    def get_test_config(
        cls,
        model: SeanergysModel,
        dataset_name: str = "colocation",
        get_dummy_data: bool = False,
    ) -> Dict[str, Tuple["ColocationPredictor", SeanergysDataloader]]:
        assert isinstance(model, ColocationPredictor)
        if dataset_name != "colocation":
            raise Exception("Invalid dataset name. Datasets allowed: 'colocation'")

        model.logger.info("Testing on the colocation dataset (30% hold-out)")
        colocation = ColocationDataset(
            use_zenodo_url=True,
            is_dummy=get_dummy_data,
            split="test",
            input_features=list(cls.FEATURES),
            output_features=[cls.TARGET],
        )
        return {
            "colocation": (model, SeanergysDataloader(dataset=colocation, batch_size=1))
        }
