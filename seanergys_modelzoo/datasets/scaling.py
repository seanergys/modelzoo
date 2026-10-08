import time
from typing import Any, ClassVar, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
from pydantic import Field, model_validator

from seanergys_modelzoo.datasets.common.seanergys_dataset import SeanergysDataset

_FILTER_OPS = {
    "==": lambda s, v: s == v,
    "=": lambda s, v: s == v,
    "!=": lambda s, v: s != v,
    ">": lambda s, v: s > v,
    ">=": lambda s, v: s >= v,
    "<": lambda s, v: s < v,
    "<=": lambda s, v: s <= v,
    "in": lambda s, v: s.isin(v),
    "not in": lambda s, v: ~s.isin(v),
}


def _filter_columns(filters: Optional[Union[List[Tuple], List[List[Tuple]]]]) -> List[str]:
    if not filters:
        return []
    groups = filters if isinstance(filters[0], list) else [filters]
    return [column for group in groups for column, _op, _val in group]


_SUPERLINEAR_COLUMNS = ["PC_X", "Time_X", "PC_Y", "Time_Y", "Target_PC", "Time_Z"]


def _superlinear_mask(df: pd.DataFrame) -> pd.Series:
    pc_b, time_b = df["Target_PC"], df["Time_Z"]
    superlinear = pd.Series(False, index=df.index)
    for pc_col, time_col in (("PC_X", "Time_X"), ("PC_Y", "Time_Y")):
        pc_a, time_a = df[pc_col], df[time_col]
        more = pc_b > pc_a
        speedup = np.where(more, time_a / time_b, time_b / time_a)
        ideal = np.where(more, pc_b / pc_a, pc_a / pc_b)
        superlinear |= speedup > ideal
    return superlinear


def _apply_filters(
    df: pd.DataFrame, filters: Optional[Union[List[Tuple], List[List[Tuple]]]]
) -> pd.DataFrame:
    if not filters:
        return df
    groups = filters if isinstance(filters[0], list) else [filters]

    mask = pd.Series(False, index=df.index)
    for group in groups:
        group_mask = pd.Series(True, index=df.index)
        for column, op, value in group:
            group_mask &= _FILTER_OPS[op](df[column], value)
        mask |= group_mask
    return df[mask]


class ScalingDataset(SeanergysDataset):
    DATASET_ID: ClassVar[str] = "scaling"

    ZENODO_URL: str = (
        "https://zenodo.org/records/23240872/files/"
        "scaling_prediction_dataset.parquet"
    )

    use_zenodo_url: bool = Field(
        default=False,
        description="If True and data_path is None, load the dataset directly from Zenodo.",
    )

    input_features: List[str] = Field(
        ..., description="List of column names to use as input features"
    )
    output_features: List[str] = Field(
        ..., description="List of column names to use as output/target features"
    )
    columns: Optional[List[str]] = Field(
        default=None,
        description="Columns to read from the CSV. If None, input_features + output_features.",
    )
    filters: Optional[Union[List[Tuple], List[List[Tuple]]]] = Field(
        default=None,
        description=(
            "Filter syntax: [[(column, op, val), ...], ...] "
            "where op is [==, =, >, >=, <, <=, !=, in, not in]. "
            "Inner tuples are ANDed; outer list is ORed."
        ),
    )
    dummy_rows: int = Field(
        default=50, description="Rows kept when is_dummy is True."
    )
    group_column: Optional[str] = Field(
        default="Benchmark",
        description=(
            "Column holding each row's group (the notebook's `groups = df['Benchmark']`), "
            "loaded alongside the features and returned by get_groups(). None disables it."
        ),
    )
    exclude_superlinear: bool = Field(
        default=False,
        description=(
            "Drop rows whose target run scales superlinearly w.r.t. the X or Y "
            "measurement (Model.ipynb cell 1; commented out there, so off by default)."
        ),
    )

    _df: Optional[pd.DataFrame] = None

    @model_validator(mode="after")
    def validate_model(self) -> "ScalingDataset":
        if self.data_path is None and self.use_zenodo_url:
            self.logger.info(f"Using Zenodo URL for scaling dataset: {self.ZENODO_URL}")
            self.data_path = self.ZENODO_URL
        elif self.data_path is None:
            raise ValueError(
                "data_path must be provided or use_zenodo_url must be True."
            )
        if self.columns is None:
            self.columns = list(
                dict.fromkeys(self.input_features + self.output_features)
            )

        assert self.metadata is not None
        self.metadata.update(
            {
                "dataset_name": "Scaling Prediction Dataset (Extrapolation)",
                "source": "Zenodo" if self.data_path == self.ZENODO_URL else "local file",
                "doi": "10.5281/zenodo.23161749",
            }
        )

        self.load_data()
        return self

    def load_data(self) -> None:
        start_time = time.time()
        assert self.data_path is not None
        self.logger.info(f"Loading scaling dataset from: {self.data_path}")

        assert self.columns is not None
        extra_columns = [self.group_column] if self.group_column else []
        if self.exclude_superlinear:
            extra_columns += _SUPERLINEAR_COLUMNS
        usecols = list(
            dict.fromkeys(self.columns + _filter_columns(self.filters) + extra_columns)
        )
        if str(self.data_path).endswith(".parquet"):
            self._df = pd.read_parquet(self.data_path, columns=usecols)
        else:
            self._df = pd.read_csv(self.data_path, usecols=usecols)
        if self.exclude_superlinear:
            self._df = self._df[~_superlinear_mask(self._df)]
        self._df = _apply_filters(self._df, self.filters)

        for fn in self.preprocessing_functions or []:
            self._df = fn(self._df)

        if self.is_dummy:
            self._df = self._df.head(self.dummy_rows).reset_index(drop=True)

        elapsed = time.time() - start_time
        self.stats.update(
            {
                "n_samples": len(self._df),
                "n_input_features": len(self.input_features),
                "n_output_features": len(self.output_features),
                "n_features": len(self.input_features),
                "load_time": elapsed,
            }
        )
        self.logger.info(
            f"{self.__class__.__name__} ready: {self.stats['n_samples']} samples "
            f"(loaded in {elapsed:.3f}s)"
        )

    def get_groups(self) -> Optional[np.ndarray]:
        if self._df is None or not self.group_column:
            return None
        return self._df[self.group_column].to_numpy()

    def __len__(self) -> int:
        return 0 if self._df is None else len(self._df)

    def __getitem__(self, idx: int) -> Tuple[Any, Any]:
        if self._df is None:
            raise RuntimeError("Data not loaded. Call load_data() first.")
        if idx >= len(self):
            raise IndexError(
                f"Index {idx} out of range for dataset of size {len(self)}"
            )

        row = self._df.iloc[idx]
        input_data: Any = row[self.input_features].values.astype(np.float64)
        output_data: Any = row[self.output_features].values.astype(np.float64)

        if self.transform is not None:
            input_data = self.transform(input_data)
        if self.target_transform is not None:
            output_data = self.target_transform(output_data)

        return input_data, output_data
