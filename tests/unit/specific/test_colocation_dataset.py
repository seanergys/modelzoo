import numpy as np
import pandas as pd
import pytest

from seanergys_modelzoo.datasets.colocation import ColocationDataset

INPUTS = ["FLOPS_A", "MPI_time_A", "FLOPS_B", "MPI_time_B"]
OUTPUTS = ["SpeedupA"]


def _frame(n: int = 20) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "BenchmarkA": [f"a_{i}" for i in range(n)],
            "FLOPS_A": [1e9 + i for i in range(n)],
            "MPI_time_A": [0.1 * i for i in range(n)],
            "BenchmarkB": [f"b_{i}" for i in range(n)],
            "FLOPS_B": [2e9 + i for i in range(n)],
            "MPI_time_B": [0.2 * i for i in range(n)],
            "SpeedupA": [1.0 + 0.01 * i for i in range(n)],
        }
    )


@pytest.fixture
def parquet_path(tmp_path):
    path = tmp_path / "colocation.parquet"
    _frame().to_parquet(path, index=False)
    return path


def _dataset(path, **kwargs) -> ColocationDataset:
    params = {
        "data_path": str(path),
        "input_features": INPUTS,
        "output_features": OUTPUTS,
    }
    params.update(kwargs)
    return ColocationDataset(**params)


def test_loads_every_row_without_split(parquet_path):
    ds = _dataset(parquet_path)
    assert len(ds) == 20
    assert ds.stats["n_samples"] == 20
    assert list(ds._df.columns) == INPUTS + OUTPUTS


def test_split_matches_pandas_sample_and_drop(parquet_path):
    df = _frame()
    expected_train = df.sample(frac=0.7, random_state=21)
    expected_test = df.drop(expected_train.index)

    train = _dataset(parquet_path, split="train")._df
    test = _dataset(parquet_path, split="test")._df

    np.testing.assert_array_equal(train["SpeedupA"], expected_train["SpeedupA"])
    np.testing.assert_array_equal(test["SpeedupA"], expected_test["SpeedupA"])


def test_validation_is_the_same_hold_out_as_test(parquet_path):
    validation = _dataset(parquet_path, split="validation")._df
    test = _dataset(parquet_path, split="test")._df
    pd.testing.assert_frame_equal(validation, test)


def test_train_and_test_partition_the_rows(parquet_path):
    train = _dataset(parquet_path, split="train")._df
    test = _dataset(parquet_path, split="test")._df
    assert len(train) + len(test) == 20
    assert set(train["FLOPS_A"]).isdisjoint(test["FLOPS_A"])


def test_split_seed_and_fraction_are_configurable(parquet_path):
    a = _dataset(parquet_path, split="train", split_seed=1, train_fraction=0.5)._df
    b = _dataset(parquet_path, split="train", split_seed=2, train_fraction=0.5)._df
    assert len(a) == len(b) == 10
    assert not a["FLOPS_A"].equals(b["FLOPS_A"])


def test_filters_apply_after_split(parquet_path):
    ds = _dataset(parquet_path, split="train", filters=[("MPI_time_A", ">", 1.0)])
    train = _dataset(parquet_path, split="train")._df
    assert len(ds) == int((train["MPI_time_A"] > 1.0).sum())
    assert "MPI_time_A" in ds._df.columns


def test_dummy_keeps_first_rows(parquet_path):
    assert len(_dataset(parquet_path, is_dummy=True, dummy_rows=5)) == 5


def test_reads_csv(tmp_path):
    path = tmp_path / "colocation.csv"
    _frame().to_csv(path, index=False)
    assert len(_dataset(path)) == 20


def test_getitem_returns_float_arrays(parquet_path):
    x, y = _dataset(parquet_path)[3]
    assert x.dtype == np.float64 and x.shape == (len(INPUTS),)
    assert y.dtype == np.float64 and y.shape == (1,)
    assert y[0] == pytest.approx(1.03)


def test_getitem_out_of_range(parquet_path):
    ds = _dataset(parquet_path)
    with pytest.raises(IndexError):
        ds[len(ds)]


def test_requires_a_source():
    with pytest.raises(ValueError, match="data_path must be provided"):
        ColocationDataset(input_features=INPUTS, output_features=OUTPUTS)


def test_zenodo_flag_sets_the_url(monkeypatch):
    monkeypatch.setattr(ColocationDataset, "load_data", lambda self: None)
    ds = ColocationDataset(
        use_zenodo_url=True, input_features=INPUTS, output_features=OUTPUTS
    )
    assert ds.data_path == ColocationDataset.model_fields["ZENODO_URL"].default
    assert ds.metadata["doi"] == "10.5281/zenodo.23342732"
