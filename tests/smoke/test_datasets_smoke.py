"""
Smoke tests: dataset discovery and (future) instantiation.

TODO: When you add real dataset sources (Zenodo paths, local files, etc.):
  - Add dataset instantiation tests with max_samples=10
  - Add tests/fixtures/ with small sample files
  - Use ci_max_samples from conftest
  - See docs/TESTING_AND_CI_PLAN.md Phase 2
"""

import pytest

# Dataset discovery needs torch (SeanergysDataset extends torch.utils.data.Dataset)
torch = pytest.importorskip("torch", reason="Dataset discovery requires torch")


def test_dataset_discovery(project_root):
    """Discover all SeanergysDataset classes. No data loading."""
    from ci.utils import retrieve_instances_from_file
    from seanergys_modelzoo.datasets.common.seanergys_dataset import SeanergysDataset

    data_folder = project_root / "seanergys_modelzoo" / "datasets"
    data_classes = {}

    for py_file in data_folder.rglob("*.py"):
        if py_file.name == "__init__.py":
            continue
        try:
            objs = retrieve_instances_from_file(py_file, SeanergysDataset)
            data_classes.update(objs)
        except Exception:
            continue

    # At least base or concrete datasets (FData, PM100, etc.)
    assert len(data_classes) >= 1, "Should find at least one SeanergysDataset subclass"


# TODO: Add when datasets support max_samples or you have real/fixture data:
# def test_dataset_instantiation_with_subset(ci_max_samples):
#     """Each dataset instantiates with max_samples=10. Requires real data source."""
#     pass
#
# def test_dataset_len_and_getitem(synthetic_dataset_fixture):
#     """Dataset __len__ and __getitem__ work. Requires synthetic or real fixture."""
#     pass
