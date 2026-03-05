"""
Fixtures for integration tests.

Uses sample_data from tests/fixtures/sample_data/ (create with `make sample-data`).
"""

from pathlib import Path

import pytest


def _integration_data_dir() -> Path:
    """Path to tests/fixtures/sample_data."""
    root = Path(__file__).resolve().parent.parent
    return root / "fixtures" / "sample_data"


@pytest.fixture
def integration_data_dir():
    """Path to tests/fixtures/sample_data. Run `make sample-data` if missing."""
    d = _integration_data_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d


@pytest.fixture
def fdata_fixture_path(integration_data_dir):
    """Path to sample_fdata.parquet."""
    return integration_data_dir / "sample_fdata.parquet"


@pytest.fixture
def fdata_dataset(fdata_fixture_path):
    """FDataDataset loaded from fixture. Skips if fixture missing."""
    if not fdata_fixture_path.exists():
        pytest.skip("No sample_fdata.parquet. Run `make sample-data`.")

    pytest.importorskip("pandas")
    pytest.importorskip("pyarrow")

    from seanergys_modelzoo.datasets.f_data import FDataDataset

    return FDataDataset(
        data_path=fdata_fixture_path,
        input_features=["nnuma", "duration"],
        output_features=["avgpcon"],
    )


@pytest.fixture
def temp_model_dir(tmp_path):
    """Temporary directory for saving models during tests."""
    return tmp_path
