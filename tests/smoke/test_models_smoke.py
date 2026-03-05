"""
Smoke tests: lightweight sanity checks (imports, discovery).
"""
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
