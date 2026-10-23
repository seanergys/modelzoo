import numpy as np
import pandas as pd
import pytest

from seanergys_modelzoo.datasets.scaling import (
    ScalingDataset,
    _apply_filters,
    _filter_columns,
)

INPUTS = ["PC_X", "PC_Y", "Target_PC", "Time_X", "Time_Y"]
OUTPUTS = ["Speedup_XZ"]


def _frame(n: int = 6) -> pd.DataFrame:
    suites = ["NPB", "Coral-2", "OSU Micro-bench"]
    return pd.DataFrame(
        {
            "Benchmark": [f"bench_{i}" for i in range(n)],
            "Suite_X": [suites[i % len(suites)] for i in range(n)],
            "PC_X": [128.0 + i for i in range(n)],
            "PC_Y": [256.0 + i for i in range(n)],
            "Target_PC": [512.0 + i for i in range(n)],
            "Time_X": [400.0 - i for i in range(n)],
            "Time_Y": [220.0 - i for i in range(n)],
            "Speedup_XZ": [2.0 + 0.1 * i for i in range(n)],
            "Unused": [0.0] * n,
        }
    )


@pytest.fixture
def csv_path(tmp_path):
    path = tmp_path / "scaling.csv"
    _frame().to_csv(path, index=False)
    return path


def _dataset(csv_path, **kwargs) -> ScalingDataset:
    params = {
        "data_path": str(csv_path),
        "input_features": INPUTS,
        "output_features": OUTPUTS,
    }
    params.update(kwargs)
    return ScalingDataset(**params)


def test_filter_columns_none_returns_empty_list():
    assert _filter_columns(None) == []
    assert _filter_columns([]) == []


def test_filter_columns_flat_and_grouped():
    assert _filter_columns([("Suite_X", "==", "NPB"), ("PC_X", ">", 1)]) == [
        "Suite_X",
        "PC_X",
    ]
    assert _filter_columns([[("Suite_X", "==", "NPB")], [("PC_Y", "<", 2)]]) == [
        "Suite_X",
        "PC_Y",
    ]


def test_apply_filters_none_returns_same_dataframe():
    df = _frame()
    assert _apply_filters(df, None) is df


@pytest.mark.parametrize(
    "op, value, expected",
    [
        ("==", "NPB", {"NPB"}),
        ("=", "NPB", {"NPB"}),
        ("!=", "NPB", {"Coral-2", "OSU Micro-bench"}),
        ("in", ["NPB", "Coral-2"], {"NPB", "Coral-2"}),
        ("not in", ["NPB", "OSU Micro-bench"], {"Coral-2"}),
    ],
)
def test_apply_filters_suite_operators(op, value, expected):
    out = _apply_filters(_frame(), [("Suite_X", op, value)])
    assert set(out["Suite_X"]) == expected


@pytest.mark.parametrize(
    "op, value, expected_pc",
    [
        (">", 130.0, [131.0, 132.0, 133.0]),
        (">=", 132.0, [132.0, 133.0]),
        ("<", 130.0, [128.0, 129.0]),
        ("<=", 128.0, [128.0]),
    ],
)
def test_apply_filters_numeric_operators(op, value, expected_pc):
    out = _apply_filters(_frame(), [("PC_X", op, value)])
    assert out["PC_X"].tolist() == expected_pc


def test_apply_filters_inner_tuples_are_anded():
    out = _apply_filters(_frame(), [("Suite_X", "==", "NPB"), ("PC_X", ">", 128.0)])
    assert out["Benchmark"].tolist() == ["bench_3"]


def test_apply_filters_outer_groups_are_ored():
    out = _apply_filters(
        _frame(), [[("Benchmark", "==", "bench_0")], [("Benchmark", "==", "bench_5")]]
    )
    assert out["Benchmark"].tolist() == ["bench_0", "bench_5"]


def test_missing_data_path_raises():
    with pytest.raises(ValueError, match="data_path must be provided"):
        ScalingDataset(input_features=INPUTS, output_features=OUTPUTS)


def test_loads_all_rows_and_sets_stats(csv_path):
    ds = _dataset(csv_path)
    assert len(ds) == 6
    assert ds.stats["n_samples"] == 6
    assert ds.stats["n_input_features"] == len(INPUTS)
    assert ds.stats["n_output_features"] == len(OUTPUTS)
    assert ds.metadata["source"] == "local file"


def test_use_zenodo_url_resolves_data_path(tmp_path, monkeypatch):
    parquet_path = tmp_path / "scaling.parquet"
    _frame().to_parquet(parquet_path, index=False)
    real_read_parquet = pd.read_parquet
    seen = []

    def fake_read_parquet(path, **kwargs):
        seen.append(path)
        return real_read_parquet(parquet_path, **kwargs)

    monkeypatch.setattr(pd, "read_parquet", fake_read_parquet)
    ds = ScalingDataset(
        use_zenodo_url=True, input_features=INPUTS, output_features=OUTPUTS
    )
    assert ds.data_path == ScalingDataset.model_fields["ZENODO_URL"].default
    assert seen == [ds.data_path]
    assert ds.metadata["source"] == "Zenodo"
    assert len(ds) == 6


def test_explicit_data_path_wins_over_zenodo(csv_path):
    ds = _dataset(csv_path, use_zenodo_url=True)
    assert ds.data_path == str(csv_path)


def test_loads_parquet_file(tmp_path):
    path = tmp_path / "scaling.parquet"
    _frame().to_parquet(path, index=False)
    ds = _dataset(path, filters=[("Suite_X", "==", "NPB")])
    assert len(ds) == 2
    assert "Unused" not in ds._df.columns


def test_default_columns_are_deduplicated_inputs_plus_outputs(csv_path):
    ds = _dataset(csv_path, input_features=INPUTS + ["PC_X"])
    assert ds.columns == INPUTS + OUTPUTS


def test_unused_columns_are_not_loaded(csv_path):
    ds = _dataset(csv_path)
    assert "Unused" not in ds._df.columns


def test_filter_column_is_read_even_if_not_a_feature(csv_path):
    ds = _dataset(csv_path, filters=[("Suite_X", "==", "NPB")])
    assert len(ds) == 2
    assert set(ds._df["Suite_X"]) == {"NPB"}


def test_train_and_test_filters_partition_the_data(csv_path):
    train = _dataset(
        csv_path, filters=[("Suite_X", "not in", ["NPB", "OSU Micro-bench"])]
    )
    test = _dataset(csv_path, filters=[("Suite_X", "in", ["NPB"])])
    train_ids = set(train._df["PC_X"])
    test_ids = set(test._df["PC_X"])
    assert train_ids and test_ids
    assert train_ids.isdisjoint(test_ids)


def test_dummy_rows_truncates(csv_path):
    ds = _dataset(csv_path, is_dummy=True, dummy_rows=3)
    assert len(ds) == 3
    assert ds._df.index.tolist() == [0, 1, 2]


def test_preprocessing_functions_applied(csv_path):
    ds = _dataset(csv_path, preprocessing_functions=[lambda df: df[df["PC_X"] < 130.0]])
    assert len(ds) == 2


def test_getitem_returns_float_arrays_in_feature_order(csv_path):
    x, y = _dataset(csv_path)[1]
    assert x.dtype == np.float64 and y.dtype == np.float64
    np.testing.assert_array_equal(x, [129.0, 257.0, 513.0, 399.0, 219.0])
    np.testing.assert_allclose(y, [2.1])


def test_getitem_before_load_raises_runtime_error(csv_path):
    ds = _dataset(csv_path)
    ds._df = None
    with pytest.raises(RuntimeError, match="Data not loaded"):
        ds[0]


def test_getitem_out_of_range_raises_index_error(csv_path):
    ds = _dataset(csv_path)
    with pytest.raises(IndexError):
        ds[len(ds)]


def test_len_is_zero_when_not_loaded(csv_path):
    ds = _dataset(csv_path)
    ds._df = None
    assert len(ds) == 0


def test_getitem_applies_transform_and_target_transform(csv_path):
    ds = _dataset(csv_path, transform=lambda x: x * 2, target_transform=lambda y: y + 1)
    x, y = ds[0]
    np.testing.assert_array_equal(x, [256.0, 512.0, 1024.0, 800.0, 440.0])
    np.testing.assert_allclose(y, [3.0])
