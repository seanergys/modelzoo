"""
Pytest configuration and shared fixtures.

TODO: When you add real dataset sources:
  - Add synthetic_dataloader fixture (torch DataLoader with fake data)
  - Add synthetic_dataset_fixture for Dataset __len__/__getitem__ tests
  - Add model_class_fixture parametrized over discovered models
  - See docs/TESTING_AND_CI_PLAN.md Phase 2-3
"""
import os
from pathlib import Path

import pytest


def pytest_configure(config):
    """Ensure project root is on Python path."""
    root = Path(__file__).resolve().parent.parent
    if str(root) not in os.environ.get("PYTHONPATH", ""):
        os.environ.setdefault("PYTHONPATH", str(root))


@pytest.fixture
def project_root() -> Path:
    """Project root directory."""
    return Path(__file__).resolve().parent.parent


@pytest.fixture
def ci_max_samples() -> int:
    """Max samples for CI/subsets. Override via env CI_MAX_SAMPLES."""
    return int(os.environ.get("CI_MAX_SAMPLES", "50"))


@pytest.fixture
def sample_data_dir(project_root) -> Path:
    """Path to tests/fixtures/sample_data/. Create with `make sample-data`."""
    d = project_root / "tests" / "fixtures" / "sample_data"
    d.mkdir(parents=True, exist_ok=True)
    return d


# TODO: Add when you add model train smoke tests:
#
# @pytest.fixture
# def synthetic_batch():
#     """Fake (X, y) batch for quick train/predict smoke. No real data file."""
#     import torch
#     return torch.randn(10, 5), torch.randn(10)
#
# @pytest.fixture
# def synthetic_dataloader(synthetic_batch):
#     """DataLoader wrapping synthetic data. For model.train(1 step) smoke."""
#     from torch.utils.data import TensorDataset, DataLoader
#     X, y = synthetic_batch
#     ds = TensorDataset(X, y)
#     return DataLoader(ds, batch_size=4)
