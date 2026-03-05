"""Unit tests for Seanergys configurator (Pydantic params)."""

import pytest


def test_model_params_instantiation():
    """SeanergysModelParams instantiates (empty is valid)."""
    from seanergys_modelzoo.models.common.seanergys_configurator import (
        SeanergysModelParams,
    )

    params = SeanergysModelParams()
    assert params is not None
    assert params.to_dict() is not None


def test_dataset_params_with_data_path():
    """SeanergysDatasetParams accepts data_path."""
    from seanergys_modelzoo.models.common.seanergys_configurator import (
        SeanergysDatasetParams,
    )

    params = SeanergysDatasetParams(data_path="/path/to/data")
    assert params.data_path == "/path/to/data"


def test_dataset_params_from_dict():
    """SeanergysDatasetParams round-trips via from_dict."""
    from seanergys_modelzoo.models.common.seanergys_configurator import (
        SeanergysDatasetParams,
    )

    config = {"data_path": "/tmp/data", "transform": None}
    params = SeanergysDatasetParams.from_dict(config)
    assert params.data_path == "/tmp/data"


def test_dataloader_params_defaults():
    """SeanergysDataloaderParams has expected defaults."""
    from seanergys_modelzoo.models.common.seanergys_configurator import (
        SeanergysDataloaderParams,
    )

    params = SeanergysDataloaderParams()
    assert params.batch_size == 1
    assert params.num_workers == 0
    assert params.shuffle is None


def test_dataloader_params_custom_batch_size():
    """SeanergysDataloaderParams accepts custom batch_size."""
    from seanergys_modelzoo.models.common.seanergys_configurator import (
        SeanergysDataloaderParams,
    )

    params = SeanergysDataloaderParams(batch_size=32)
    assert params.batch_size == 32
