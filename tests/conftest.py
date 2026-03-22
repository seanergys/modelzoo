"""
Pytest configuration and shared fixtures.
"""

import os
from pathlib import Path
from typing import Dict, Type

import pytest


# ---------------------------------------------------------------------------
# Project root
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def pytest_configure(config):
    """Ensure project root is on Python path."""
    root = str(_PROJECT_ROOT)
    if root not in os.environ.get("PYTHONPATH", ""):
        os.environ.setdefault("PYTHONPATH", root)


# ---------------------------------------------------------------------------
# Model discovery (runs at collection time, used to parametrize tests)
# ---------------------------------------------------------------------------


def _collect_model_classes() -> Dict[str, Type]:
    """
    Discover all concrete SeanergysModel subclasses in models/tasks/.

    Skips base/abstract classes. Returns empty dict if deps are missing.
    Only looks under models/tasks/ so base classes are never included.
    """
    try:
        from ci.utils import retrieve_instances_from_file
        from seanergys_modelzoo.models.common.seanergys_model import SeanergysModel
    except ImportError:
        return {}

    tasks_folder = _PROJECT_ROOT / "seanergys_modelzoo" / "models" / "tasks"
    classes: Dict[str, Type] = {}

    for py_file in tasks_folder.rglob("*.py"):
        if py_file.name == "__init__.py":
            continue
        try:
            objs = retrieve_instances_from_file(py_file, SeanergysModel)
            classes.update(objs)
        except Exception:
            continue

    return classes


# Collected once at session start. Used by parametrize in integration tests.
MODEL_CLASSES = _collect_model_classes()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def project_root() -> Path:
    """Project root directory."""
    return _PROJECT_ROOT


@pytest.fixture(scope="session")
def ci_max_samples() -> int:
    """Max samples for CI runs. Override via env CI_MAX_SAMPLES."""
    return int(os.environ.get("CI_MAX_SAMPLES", "50"))


@pytest.fixture(scope="session")
def sample_data_dir(project_root) -> Path:
    """Path to tests/fixtures/sample_data/. Create with `make sample-data`."""
    d = project_root / "tests" / "fixtures" / "sample_data"
    d.mkdir(parents=True, exist_ok=True)
    return d
