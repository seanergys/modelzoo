"""
Smoke tests: load datasets via Python API (Option 2).

- test_load_*_from_local_fixtures: use pre-created sample files (run `make sample-data` first).
- test_load_*_from_zenodo: fetch from Zenodo (requires network; skipped if CI_SKIP_ZENODO=1).
"""

import os
from pathlib import Path

import pytest


def _fixtures_dir(project_root: Path) -> Path:
    return project_root / "tests" / "fixtures" / "sample_data"


def _has_fixtures(project_root: Path) -> bool:
    d = _fixtures_dir(project_root)
    return (d / "sample_fdata.parquet").exists() or (
        d / "sample_pm100.parquet"
    ).exists()


# -----------------------------------------------------------------------------
# Load from local fixtures (no network)
# -----------------------------------------------------------------------------


def test_load_fdata_from_local_fixtures(project_root, sample_data_dir):
    """
    Load F-DATA from local sample file.
    Run `make sample-data` first to create fixtures.
    """
    fixture = sample_data_dir / "sample_fdata.parquet"
    if not fixture.exists():
        pytest.skip(
            "No sample_fdata.parquet. Run `make sample-data` to create fixtures."
        )

    pytest.importorskip("pandas")
    pytest.importorskip("pyarrow")

    from seanergys_modelzoo.datasets.f_data import FDataDataset

    # F-DATA schema: nnuma (nodes), duration, avgpcon (avg power consumption)
    ds = FDataDataset(
        data_path=fixture,
        input_features=["nnuma", "duration"],
        output_features=["avgpcon"],
    )
    assert len(ds) >= 1
    x, y = ds[0]
    assert x is not None
    assert y is not None


def test_load_pm100_from_local_fixtures(project_root, sample_data_dir):
    """
    Load PM100 from local sample file.
    Run `make sample-data` first to create fixtures.
    """
    fixture = sample_data_dir / "sample_pm100.parquet"
    if not fixture.exists():
        pytest.skip(
            "No sample_pm100.parquet. Run `make sample-data` to create fixtures."
        )

    pytest.importorskip("pandas")
    pytest.importorskip("pyarrow")

    # PM100 schema varies; use columns from create_sample_data output
    import pandas as pd

    from seanergys_modelzoo.datasets.pm100 import PM100Dataset

    cols = pd.read_parquet(fixture).columns.tolist()
    if len(cols) < 2:
        pytest.skip(f"Sample has <2 columns: {cols}")
    in_cols, out_cols = cols[: len(cols) // 2], cols[len(cols) // 2 :]
    if not out_cols:
        out_cols = [cols[-1]] if len(cols) > 1 else [cols[0]]
        in_cols = cols[: len(cols) - 1]
    ds = PM100Dataset(
        data_path=fixture,
        input_features=in_cols[:2],
        output_features=out_cols[:1],
    )
    assert len(ds) >= 1
    x, y = ds[0]
    assert x is not None
    assert y is not None


# -----------------------------------------------------------------------------
# Load from Zenodo (requires network)
# -----------------------------------------------------------------------------


@pytest.mark.zenodo
def test_load_fdata_from_zenodo():
    """
    Load F-DATA directly from Zenodo via Python API (Option 2).
    Requires network. Skipped if CI_SKIP_ZENODO=1.
    """
    if os.environ.get("CI_SKIP_ZENODO") == "1":
        pytest.skip("CI_SKIP_ZENODO=1: skip Zenodo tests")

    pytest.importorskip("pandas")
    pytest.importorskip("pyarrow")

    from seanergys_modelzoo.datasets.f_data import FDataDataset

    ds = FDataDataset(
        use_zenodo_url=True,
        files="21_04",
        input_features=["nnuma", "duration"],
        output_features=["avgpcon"],
    )
    assert len(ds) >= 1
    x, y = ds[0]
    assert x is not None
    assert y is not None


@pytest.mark.zenodo
def test_load_pm100_from_zenodo():
    """
    Load PM100 directly from Zenodo via Python API (Option 2).
    Requires network. Skipped if CI_SKIP_ZENODO=1.
    """
    if os.environ.get("CI_SKIP_ZENODO") == "1":
        pytest.skip("CI_SKIP_ZENODO=1: skip Zenodo tests")

    pytest.importorskip("pandas")
    pytest.importorskip("pyarrow")

    from seanergys_modelzoo.datasets.pm100 import PM100Dataset

    # PM100 from Zenodo - use numeric columns only (no categorical preprocessing)
    ds = PM100Dataset(
        use_zenodo_url=True,
        input_features=["num_nodes_req", "elapsed_time"],
        output_features=["num_nodes_alloc"],
    )
    assert len(ds) >= 1
    x, y = ds[0]
    assert x is not None
    assert y is not None
