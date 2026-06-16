"""
Module for preprocessing the Iris dataset.
"""

from sklearn.preprocessing import OrdinalEncoder
from sentence_transformers import SentenceTransformer
from sklearn.base import BaseEstimator, TransformerMixin
import os

from sklearn.model_selection import train_test_split
from typing import Tuple
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, StandardScaler


def split_data(
        X: np.ndarray,
        y: np.ndarray,
        test_size: float = 0.2,
        random_state: int = 42,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Splits the Iris dataset into training and testing sets.

    Args:
        - X (np.ndarray): Features.
        - y (np.ndarray): Target.
        - test_size (float, optional): The proportion of the dataset to include in the test split. Defaults to 0.2.
        - random_state (int, optional): Controls the shuffling applied to the data before splitting. Defaults to 42.

    Returns:
        Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
            A tuple containing:
                - X_train: Training features.
                - X_test: Testing features.
                - y_train: Training target.
                - y_test: Testing target.
    """
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=random_state
    )
    return X_train, X_test, y_train, y_test


class SBERTEncoder(BaseEstimator, TransformerMixin):
    """Custom transformer to encode text columns with SBERT embeddings (sklearn-clone safe)."""

    def __init__(
        self,
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        device: str | None = None,             # "cuda" | "cpu" | None(auto)
        env_var_path: str = "SBERT_MODEL_DIR", # if set, load from this local folder
        batch_size: int = 512,                 # batching for memory safety
        normalize: bool = False,               # L2-normalize embeddings
        dtype: str = "float32",                # keep as string to pass sklearn clone check
    ):
        self.model_name = model_name
        self.device = device
        self.env_var_path = env_var_path
        self.batch_size = batch_size
        self.normalize = normalize
        self.dtype = dtype

        self._model = None
        self._dtype_np = None

    def _resolve_model_source(self) -> str:
        local_dir = os.getenv(self.env_var_path)
        return local_dir if local_dir else self.model_name

    def fit(self, X, y=None):
        if self._model is None:
            source = self._resolve_model_source()
            self._model = SentenceTransformer(source, device=self.device)
        # derive numpy dtype here (not in __init__)
        if self.dtype not in ("float32", "float64"):
            raise ValueError("dtype must be 'float32' or 'float64'")
        self._dtype_np = np.float32 if self.dtype == "float32" else np.float64
        return self

    def transform(self, X):
        # Accept DataFrame/ndarray/list; use first column if DataFrame
        if isinstance(X, pd.DataFrame):
            texts = X.iloc[:, 0].tolist()
        elif hasattr(X, "ravel"):
            texts = X.ravel().tolist()
        else:
            texts = list(X)
        texts = ["" if t is None else str(t) for t in texts]

        emb = self._model.encode(
            texts,
            batch_size=self.batch_size,
            convert_to_numpy=True,
            normalize_embeddings=self.normalize,
            show_progress_bar=False,
        )
        if emb.dtype != self._dtype_np:
            emb = emb.astype(self._dtype_np, copy=False)
        return emb


def build_preprocessor(categorical, numeric,
                       mode: str = "full",
                       cat_strategy: str = "onehot") -> ColumnTransformer:
    """
    Create a preprocessing pipeline for categorical and numerical features.

    Modes:
        - "full": process categorical + scale numeric
        - "numeric_only": pass numeric through unchanged
        - "none": pass everything through unchanged

    cat_strategy:
        - "onehot": OneHotEncoder for categorical
        - "ordinal": OrdinalEncoder for categorical
        - "sbert": Sentence-BERT embeddings for categorical
    """
    transformers = []

    if mode == "full":
        # Handle categorical features
        if categorical:
            if cat_strategy == "onehot":
                transformers.append(("cat", OneHotEncoder(handle_unknown="ignore"), categorical))
            elif cat_strategy == "ordinal":
                transformers.append(("cat", OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1), categorical))
            elif cat_strategy == "sbert":
                for col in categorical:  # SBERT must be applied per text column
                    transformers.append((f"sbert_{col}", SBERTEncoder(), [col]))
            else:
                raise ValueError(f"Unknown cat_strategy: {cat_strategy}")

        # Handle numeric features
        if numeric:
            transformers.append(("num", StandardScaler(), numeric))

    elif mode == "numeric_only":
        # transformers.append(("num", "passthrough", numeric))
        transformers.append(("num", StandardScaler(), numeric))

    elif mode == "none":
        transformers.append(("all", "passthrough", (categorical or []) + (numeric or [])))

    else:
        raise ValueError(f"Unknown mode: {mode}. Use 'full', 'numeric_only', or 'none'.")

    return ColumnTransformer(transformers)


def one_hot_to_numeric(one_hot_array: np.ndarray) -> np.ndarray:
    """
    Convert a one-hot encoded array into its numeric (class index) representation.

    Args:
    - one_hot_array : numpy.ndarray of shape (n_samples, n_classes), it is the one-hot encoded data.

    Returns:
    - numpy.ndarray of shape (n_samples,) numeric representation of the one-hot data.
    """
    return np.argmax(one_hot_array, axis=1)