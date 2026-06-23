"""Unit tests for dataset file/node-spec parsing logic.

These parsers (M100Dataset, FDataDataset) are pure functions over class-level
file tables. They are exercised via ``model_construct`` so instantiation does
not trigger ``validate_model`` (which would download from Zenodo).
"""

import pytest

pytest.importorskip("torch")
pytest.importorskip("pyarrow")
pytest.importorskip("cachetools")

from seanergys_modelzoo.datasets.f_data import FDataDataset  # noqa: E402
from seanergys_modelzoo.datasets.m100 import M100Dataset  # noqa: E402


# ---------------------------------------------------------------------------
# M100Dataset._parse_nodes
# ---------------------------------------------------------------------------


def test_parse_nodes_none():
    assert M100Dataset.model_construct(nodes=None)._parse_nodes() is None


def test_parse_nodes_single_int():
    assert M100Dataset.model_construct(nodes=7)._parse_nodes() == [7]


def test_parse_nodes_range_string():
    assert M100Dataset.model_construct(nodes="5:10")._parse_nodes() == [
        5,
        6,
        7,
        8,
        9,
        10,
    ]


def test_parse_nodes_single_string():
    assert M100Dataset.model_construct(nodes="3")._parse_nodes() == [3]


def test_parse_nodes_mixed_list():
    assert M100Dataset.model_construct(nodes=[1, "3:5", 10])._parse_nodes() == [
        1,
        3,
        4,
        5,
        10,
    ]


def test_parse_nodes_all():
    nodes = M100Dataset.model_construct(nodes="all")._parse_nodes()
    assert nodes == list(range(1000))


def test_get_total_nodes():
    assert M100Dataset.model_construct()._get_total_nodes() == 1000


# ---------------------------------------------------------------------------
# M100Dataset._build_file_list
# ---------------------------------------------------------------------------


def test_build_file_list_aggregated_maps_nodes_to_racks():
    ds = M100Dataset.model_construct()
    ds._nodes = [0, 25, 40]  # racks 0, 1, 2
    files = ds._build_file_list(None, aggregated=True)
    assert files == [("7541722", "0"), ("7541722", "1"), ("7541722", "2")]


def test_build_file_list_aggregated_fallback_all_racks():
    ds = M100Dataset.model_construct()
    ds._nodes = []
    files = ds._build_file_list(None, aggregated=True)
    assert len(files) == 50
    assert all(rid == "7541722" for rid, _ in files)


def test_build_file_list_raw_single():
    ds = M100Dataset.model_construct()
    ds._nodes = []
    assert ds._build_file_list("22-02", aggregated=False) == [("7589942", "22-02")]


def test_build_file_list_raw_range():
    ds = M100Dataset.model_construct()
    ds._nodes = []
    files = ds._build_file_list("20-03:20-05", aggregated=False)
    assert files == [
        ("7588815", "20-03"),
        ("7588815", "20-04"),
        ("7588815", "20-05"),
    ]


def test_build_file_list_raw_list():
    ds = M100Dataset.model_construct()
    ds._nodes = []
    files = ds._build_file_list(["20-03", "21-01"], aggregated=False)
    assert files == [("7588815", "20-03"), ("7589131", "21-01")]


def test_build_file_list_raw_all():
    ds = M100Dataset.model_construct()
    ds._nodes = []
    files = ds._build_file_list(None, aggregated=False)
    # all non-aggregated months
    assert ("7589942", "22-02") in files
    assert all(rid != "7541722" for rid, _ in files)


def test_build_file_list_invalid_type_raises():
    ds = M100Dataset.model_construct()
    ds._nodes = []
    with pytest.raises(TypeError):
        ds._build_file_list(123, aggregated=False)


# ---------------------------------------------------------------------------
# FDataDataset._parse_files_parameter
# ---------------------------------------------------------------------------


def test_fdata_parse_files_none_returns_all():
    ds = FDataDataset.model_construct()
    assert ds._parse_files_parameter(None) == ds.AVAILABLE_FILES


def test_fdata_parse_files_all_string():
    ds = FDataDataset.model_construct()
    assert ds._parse_files_parameter("all") == ds.AVAILABLE_FILES


def test_fdata_parse_files_single():
    ds = FDataDataset.model_construct()
    assert ds._parse_files_parameter("21_03") == ["21_03"]


def test_fdata_parse_files_single_strips_extension():
    ds = FDataDataset.model_construct()
    assert ds._parse_files_parameter("21_03.parquet") == ["21_03"]


def test_fdata_parse_files_range():
    ds = FDataDataset.model_construct()
    assert ds._parse_files_parameter("21_03:21_05") == ["21_03", "21_04", "21_05"]


def test_fdata_parse_files_list():
    ds = FDataDataset.model_construct()
    assert ds._parse_files_parameter(["21_03", "21_04"]) == ["21_03", "21_04"]


def test_fdata_parse_files_invalid_single_raises():
    ds = FDataDataset.model_construct()
    with pytest.raises(ValueError):
        ds._parse_files_parameter("99_99")


def test_fdata_parse_files_invalid_range_raises():
    ds = FDataDataset.model_construct()
    with pytest.raises(ValueError):
        ds._parse_files_parameter("21_03:99_99")


def test_fdata_parse_files_invalid_list_raises():
    ds = FDataDataset.model_construct()
    with pytest.raises(ValueError):
        ds._parse_files_parameter(["21_03", "nope"])


def test_fdata_parse_files_invalid_type_raises():
    ds = FDataDataset.model_construct()
    with pytest.raises(TypeError):
        ds._parse_files_parameter(123)
