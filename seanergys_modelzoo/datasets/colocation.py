import time
from typing import Any, ClassVar, List, Literal, Optional, Tuple, Union

import numpy as np
import pandas as pd
from pydantic import Field, model_validator

from seanergys_modelzoo.datasets.common.seanergys_dataset import SeanergysDataset
from seanergys_modelzoo.datasets.scaling import _apply_filters, _filter_columns


class ColocationDataset(SeanergysDataset):
    """Pairs of co-located HPC benchmarks (A, B) and the speedup of A (``SpeedupA``).

    One row per (BenchmarkA, BenchmarkB) combination: FLOPS, memory traffic,
    LLC misses/hits and MPI time of each side, plus the target. The file on
    Zenodo is already shuffled; ``split`` reproduces the notebook's
    ``full.sample(frac=0.7, random_state=21)`` / ``full.drop(train.index)``.
    """

    DATASET_ID: ClassVar[str] = "colocation"

    ZENODO_URL: str = (
        "https://zenodo.org/records/23342732/files/"
        "shuffled_unnormalized_benchmark_combinations_for_regression.parquet"
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
        description="Columns to read. If None, input_features + output_features.",
    )
    filters: Optional[Union[List[Tuple], List[List[Tuple]]]] = Field(
        default=None,
        description=(
            "Filter syntax: [[(column, op, val), ...], ...] "
            "where op is [==, =, >, >=, <, <=, !=, in, not in]. "
            "Inner tuples are ANDed; outer list is ORed."
        ),
    )
    split: Optional[Literal["train", "validation", "test"]] = Field(
        default=None,
        description=(
            "'train' = the random train_fraction sample, 'validation'/'test' = the "
            "remaining rows, None = every row. Drawn before filters are applied."
        ),
    )
    train_fraction: float = Field(
        default=0.7, gt=0.0, lt=1.0, description="Share of rows in the 'train' split."
    )
    split_seed: int = Field(
        default=21,
        description="random_state of the train/test sample (notebook: seed = 21).",
    )
    dummy_rows: int = Field(default=50, description="Rows kept when is_dummy is True.")

    _df: Optional[pd.DataFrame] = None

    @model_validator(mode="after")
    def validate_model(self) -> "ColocationDataset":
        if self.data_path is None and self.use_zenodo_url:
            self.logger.info(
                f"Using Zenodo URL for colocation dataset: {self.ZENODO_URL}"
            )
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
                "dataset_name": "Co-location prediction dataset",
                "source": "Zenodo"
                if self.data_path == self.ZENODO_URL
                else "local file",
                "doi": "10.5281/zenodo.23342732",
            }
        )

        self.load_data()
        return self

    def load_data(self) -> None:
        start_time = time.time()
        assert self.data_path is not None
        self.logger.info(f"Loading colocation dataset from: {self.data_path}")

        assert self.columns is not None
        usecols = list(dict.fromkeys(self.columns + _filter_columns(self.filters)))
        if str(self.data_path).endswith(".csv"):
            df = pd.read_csv(self.data_path, usecols=usecols)
        else:
            df = pd.read_parquet(self.data_path, columns=usecols)

        if self.split is not None:
            train = df.sample(frac=self.train_fraction, random_state=self.split_seed)
            df = train if self.split == "train" else df.drop(train.index)

        df = _apply_filters(df, self.filters)

        for fn in self.preprocessing_functions or []:
            df = fn(df)

        if self.is_dummy:
            df = df.head(self.dummy_rows)

        self._df = df.reset_index(drop=True)

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
            f"(split={self.split}, loaded in {elapsed:.3f}s)"
        )

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
