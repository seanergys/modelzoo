"""
Smoke tests: imports, discovery, (future) model instantiation.

TODO: When you add real dataset sources / max_samples support:
  - Add model instantiation tests with minimal config
  - Add train(1 step) smoke with synthetic data
  - See docs/TESTING_AND_CI_PLAN.md Phase 2
"""
from pathlib import Path

import pytest


def test_logger_imports():
    """SeanergysLogger can be imported and instantiated."""
    from seanergys_modelzoo.logger.seanergys_logger import SeanergysLogger

    logger = SeanergysLogger()
    assert logger is not None


def test_ci_utils_imports():
    """ci.utils discovery helpers can be imported."""
    from ci.utils import import_module_from_file, retrieve_instances_from_file

    assert callable(import_module_from_file)
    assert callable(retrieve_instances_from_file)


def test_model_discovery(project_root):
    """
    Discover all SeanergysModel classes. Requires full deps (torch, sklearn, etc).
    Skipped if deps missing (use ci/requirements-ci.txt for full run).
    """
    pytest.importorskip("torch", reason="Model discovery requires torch")
    pytest.importorskip("sklearn", reason="Model discovery requires sklearn")
    from ci.utils import retrieve_instances_from_file
    from seanergys_modelzoo.models.common.seanergys_model import SeanergysModel

    model_folder = project_root / "seanergys_modelzoo" / "models"
    model_classes = {}

    for py_file in model_folder.rglob("*.py"):
        try:
            objs = retrieve_instances_from_file(py_file, SeanergysModel)
            model_classes.update(objs)
        except Exception:
            continue

    assert len(model_classes) >= 1, "Should find at least one SeanergysModel subclass"


# TODO: Add when you have synthetic data or max_samples on datasets:
# def test_model_instantiation(model_class_fixture):
#     """Each model instantiates with minimal config. No training."""
#     pass
#
# def test_model_train_one_step(model_instance, synthetic_dataloader):
#     """model.train() runs 1 step. Requires data (synthetic or subset)."""
#     pass
