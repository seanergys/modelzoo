"""
Duration Prediction model for the Seanergys Model Zoo.

This module defines the Seanergys wrapper used to train, evaluate,
predict, save and load the Duration Prediction model on F-DATA.

Responsibilities:
- Define train and test configurations for FDataDataset
- Prepare F-DATA records for duration prediction
- Train and evaluate the DurationModel through the Seanergys interface
- Persist the trained model and preprocessing state

Predictions are returned in minutes.
Walltime (elpl) is internally converted from seconds to minutes
during preprocessing.
"""

from pathlib import Path
from typing import Any, Dict, cast

import joblib
import numpy as np
import pandas as pd
from pydantic import model_validator

from seanergys_modelzoo.dataloader.seanergys_dataloader import SeanergysDataloader
from seanergys_modelzoo.datasets.f_data import FDataDataset
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
from seanergys_modelzoo.models.tasks.duration_prediction.duration_prediction_bull.evaluation.metrics import (
    create_metrics,
)
from seanergys_modelzoo.models.tasks.duration_prediction.duration_prediction_bull.models.duration_model import (
    DurationModel,
)
from seanergys_modelzoo.models.tasks.duration_prediction.duration_prediction_bull.preprocessing.data_preparation import (
    prepare_duration_dataframe,
)
from seanergys_modelzoo.models.tasks.duration_prediction.duration_prediction_bull.preprocessing.duration_preprocessor import (
    DurationPreprocessor,
)


class _DurationEstimator:
    """joblib-picklable (ensemble, fitted preprocessor) pair.

    This is the `.estimator` surface the generic sklearn-flavoured Slurm
    pipeline (slurm_submit_task's joblib.dump, the default
    SklearnFrameworkAdapter used by result_fetch_task, and evaluate_task's
    `model.estimator.predict(...)`) expects. DurationPredictionBull's own
    train()/evaluate()/predict() stay DataFrame-based and unaffected â€” this
    is only a bridge for the pipeline machinery that reaches for `.estimator`
    directly instead of calling DurationPredictionBull's methods.
    """

    def __init__(
        self, model: "DurationModel", preprocessor: "DurationPreprocessor"
    ) -> None:
        self.model = model
        self.preprocessor = preprocessor

    def predict(self, X) -> np.ndarray:
        """
        Predict job duration (minutes) from either:
          - a pandas DataFrame already carrying emb_*/cnumr/nnumr/elpl
            columns (what evaluate_task's _extract_data_from_loader hands
            us), or
          - a flat numpy array / list of rows â€” what Ray Serve's /predict
            endpoint actually sends: request.features' values flattened, in
            order, with no column names. Real inference traffic arrives
            this way, so this method has to accept it directly.

        For the flat-array case, columns are rebuilt in the same order the
        model was trained on â€” embedding values first, then cnumr, nnumr,
        elpl â€” using the fitted preprocessor's own record of how many
        embedding columns there are (self.preprocessor.emb_cols), so the
        split point doesn't need to be guessed or hardcoded.
        """
        if isinstance(X, pd.DataFrame):
            df = X
        else:
            arr = np.asarray(X, dtype=float)
            if arr.ndim == 1:
                arr = arr.reshape(1, -1)

            emb_cols = self.preprocessor.emb_cols
            expected = len(emb_cols) + 3  # + cnumr, nnumr, elpl
            if arr.shape[1] != expected:
                raise ValueError(
                    f"_DurationEstimator.predict expected {expected} columns "
                    f"(embedding x{len(emb_cols)} + cnumr, nnumr, elpl); "
                    f"got {arr.shape[1]}"
                )

            df = pd.DataFrame(arr[:, : len(emb_cols)], columns=emb_cols)
            df["cnumr"] = arr[:, len(emb_cols)]
            df["nnumr"] = arr[:, len(emb_cols) + 1]
            df["elpl"] = arr[:, len(emb_cols) + 2]

        X_processed = self.preprocessor.transform(df)
        return self.model.predict(X_processed)


class DurationPredictionBull(SeanergysModel):
    """
    Seanergys Model Zoo wrapper for duration prediction.

    This class connects FDataDataset, the duration preprocessing pipeline,
    and DurationModel into the interface expected by Seanergys models.
    """

    @staticmethod
    def flatten_input_sample(sample: np.ndarray) -> np.ndarray:
        """
        Flatten an F-DATA duration-prediction sample into a numeric vector.

        The raw sample contains:
            [embedding, cnumr, nnumr, elpl]

        where embedding is a vector and the remaining features are scalars.

        Returns:
            np.ndarray:
                Numeric float32 vector containing the embedding followed by
                cnumr, nnumr and elpl.
        """
        embedding = np.asarray(sample[0], dtype=np.float32).reshape(-1)

        numeric_features = np.asarray(
            sample[1:],
            dtype=np.float32,
        )

        return np.concatenate([embedding, numeric_features]).astype(np.float32)

    @classmethod
    def get_train_config(
        cls,
        dataset_name: str = "f-data",
        get_dummy_data: bool = False,
    ) -> Dict[str, Any]:
        """
        Build the training configuration used by the Seanergys pipeline.

        Args:
            dataset_name (str):
                Dataset identifier.
            get_dummy_data (bool):
                Whether to load a lightweight dummy dataset.

        Returns:
            Dict[str, Any]:
                Training configuration.
        """
        if dataset_name != "f-data":
            raise ValueError("Invalid dataset name. Allowed dataset: 'f-data'.")

        model_fdata = cls(task_type=SeanergysModelTask.REGRESSION)

        ds_params = SeanergysDatasetParams(
            use_zenodo_url=not get_dummy_data,
            is_dummy=get_dummy_data,
            files=[] if get_dummy_data else ["21_04"],
            transform=model_fdata.flatten_input_sample,
            input_features=[
                "embedding",
                "cnumr",
                "nnumr",
                "elpl",
            ],
            output_features=["duration"],
        )

        dl_params = SeanergysDataloaderParams(
            batch_size=64,
            shuffle=True,
        )

        return {
            dataset_name: (
                model_fdata,
                FDataDataset,
                (
                    ds_params,
                    dl_params,
                ),
            )
        }

    @model_validator(mode="before")
    @classmethod
    def _inject_defaults(
        cls,
        values: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Inject default Seanergys configuration.

        Args:
            values (dict):
                Model initialization values.

        Returns:
            dict:
                Updated initialization values.
        """
        values.setdefault(
            "task_type",
            SeanergysModelTask.REGRESSION,
        )

        values.setdefault(
            "supported_datasets",
            [FDataDataset],
        )

        values.setdefault(
            "metadata",
            SeanergysModelMetadata(name="DurationPredictionBull"),
        )

        return values

    @model_validator(mode="after")
    def validate_model(self) -> "DurationPredictionBull":
        """
        Validate the model configuration.

        Returns:
            DurationPredictionBull:
                Validated model instance.
        """
        return self

    def evaluate(
        self,
        data_loader,
    ):
        """
        Evaluate the duration prediction model.

        Args:
            data_loader:
                Seanergys dataloader containing evaluation samples.

        Returns:
            Dict[str, float]:
                Dictionary containing evaluation metrics.
        """
        if not self.is_trained:
            raise RuntimeError("Model must be trained before prediction.")
        df = data_loader.dataset._df.copy()

        df = prepare_duration_dataframe(df)

        X = self.preprocessor.transform(df)

        y = df["duration_job"].values.astype(float) / 60.0

        y_pred = self.model.predict(X)

        return create_metrics(
            y_true=y,
            preds=y_pred,
        )

    def train(
        self,
        train_data_loader: SeanergysDataloader,
        val_data_loader: SeanergysDataloader | None = None,
        training_loss=None,
        validation_metrics=None,
        **kwargs,
    ) -> dict[str, list[float]]:
        """
        Train the duration prediction model from a Seanergys dataloader.
        Args:
            train_data_loader:
                Seanergys dataloader containing training samples.
            val_data_loader:
                Optional Seanergys dataloader containing validation samples.

        Returns:
            None.
        """

        train_dataset = cast(FDataDataset, train_data_loader.dataset)
        assert train_dataset._df is not None, (
            "train_data_loader.dataset has no loaded data"
        )
        train_df = train_dataset._df.copy()

        train_df = prepare_duration_dataframe(train_df)

        self.preprocessor.fit(train_df)

        X_train = self.preprocessor.transform(train_df)

        y_train = train_df["duration_job"].values

        validation_data = None

        if val_data_loader is not None:
            val_dataset = cast(FDataDataset, val_data_loader.dataset)
            assert val_dataset._df is not None, (
                "val_data_loader.dataset has no loaded data"
            )
            val_df = val_dataset._df.copy()

            val_df = prepare_duration_dataframe(val_df)

            X_val = self.preprocessor.transform(val_df)

            y_val = val_df["duration_job"].values

            validation_data = (X_val, y_val)

        self.model.fit(
            X_train,
            y_train,
            validation_data=validation_data,
        )

        self.is_trained = True
        self.estimator = _DurationEstimator(self.model, self.preprocessor)

        return {}

    def _extract_data_from_loader(self, dataloader: SeanergysDataloader):
        """
        Bridge for the generic Slurm/estimator pipeline (evaluate_task,
        result_fetch_task): __getitem__ can't handle these mixed
        embedding + scalar input_features (it casts the raw row to float
        before any transform runs), so â€” same as train()/evaluate() â€” pull
        straight from the underlying DataFrame instead of iterating items.

        Returns:
            (pd.DataFrame, np.ndarray): the DataFrame expected by
            _DurationEstimator.predict(), and targets in minutes (matching
            evaluate()'s units).
        """
        df = dataloader.dataset._df.copy()

        df = prepare_duration_dataframe(df)

        y = df["duration_job"].values.astype(float) / 60.0

        return df, y

    @classmethod
    def get_test_config(
        cls,
        model,
        dataset_name: str = "f-data",
        get_dummy_data: bool = False,
    ) -> Dict[str, Any]:
        """
        Build the evaluation configuration used by the Seanergys pipeline.

        Args:
            model:
                Trained model instance.
            dataset_name (str):
                Dataset identifier.
            get_dummy_data (bool):
                Whether to load a lightweight dummy dataset.

        Returns:
            Dict[str, Any]:
                Evaluation configuration.
        """
        if dataset_name != "f-data":
            raise ValueError("Invalid dataset name. Allowed dataset: 'f-data'.")

        dataset = FDataDataset(
            use_zenodo_url=not get_dummy_data,
            is_dummy=get_dummy_data,
            files=[] if get_dummy_data else ["21_04"],
            transform=model.flatten_input_sample,
            input_features=[
                "embedding",
                "cnumr",
                "nnumr",
                "elpl",
            ],
            output_features=["duration"],
        )

        data_loader = SeanergysDataloader(
            dataset=dataset,
            batch_size=64,
            shuffle=False,
        )

        return {
            dataset_name: (
                model,
                data_loader,
            )
        }

    def model_post_init(self, __context: Any) -> None:
        """
        Pydantic post-initialization hook.

        Automatically builds the underlying duration prediction
        model and associated preprocessor after object creation.

        Args:
            __context (Any):
                Pydantic initialization context.

        Returns:
            None.
        """

        super().model_post_init(__context)

        self.build_model()

    def build_model(self) -> None:
        """
        Initialize the duration prediction model and its preprocessor.

        Returns:
            None.
        """
        self.model = DurationModel()
        self.preprocessor = DurationPreprocessor()

    def predict(
        self,
        data_loader,
    ):
        """
        Generate duration predictions from a Seanergys dataloader.

        Args:
            data_loader:
                Seanergys dataloader containing inference samples.

        Returns:
            np.ndarray:
                Predicted job durations.
        """
        if not self.is_trained:
            raise RuntimeError("Model must be trained before prediction.")

        df = data_loader.dataset._df.copy()

        df = prepare_duration_dataframe(df, require_target=False)

        X = self.preprocessor.transform(df)

        return self.model.predict(X)

    def save(self, path: str | Path, **kwargs) -> bool:
        """
        Save the trained duration prediction model to disk.

        Args:
            path (str):
                Destination directory.

        Returns:
            bool:
                True if the model was successfully saved, False otherwise.
        """
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)

        try:
            joblib.dump(
                {
                    "model": self.model,
                    "preprocessor": self.preprocessor,
                    "is_trained": self.is_trained,
                    "metadata": self.metadata,
                },
                path / "duration_prediction_bull.joblib",
            )
            return True
        except Exception as e:
            self.logger.error(f"Error saving model: {e}")
            return False

    @classmethod
    def load(
        cls,
        path: str | Path,
        **kwargs,
    ) -> "DurationPredictionBull":
        """
        Load a saved DurationPredictionBull model from disk.

        Args:
            path (str):
                Path to the saved model directory.

        Returns:
            DurationPredictionBull:
                Loaded duration prediction model.
        """
        path = Path(path)

        data = joblib.load(path / "duration_prediction_bull.joblib")

        obj = cls(task_type=SeanergysModelTask.REGRESSION)

        obj.model = data["model"]
        obj.preprocessor = data["preprocessor"]
        obj.is_trained = data.get("is_trained", True)
        obj.metadata = data.get("metadata", obj.metadata)

        return obj
