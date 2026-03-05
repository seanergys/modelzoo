"""
Pytest configuration and shared fixtures.
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
