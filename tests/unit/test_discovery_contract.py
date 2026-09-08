"""
The discovery contract: whatever a developer adds must be tested automatically.

This module is the guard for the modelzoo's central promise — a developer writes
a new model or dataset against SeanergysModel / SeanergysDataset, and CI picks it
up and exercises it WITHOUT anyone editing a test. Auto-discovery already finds
new classes; what was missing is anything that fails when a discovered class is
never actually exercised. A dataset could be discovered, contribute zero test
cases, and the pipeline would still report green.

Nothing here names a concrete model or dataset. Every case is derived from:

  * tests/conftest.MODEL_CLASSES / DATASET_CLASSES  (auto-discovery)
  * each model's get_train_config() / supported_datasets  (the author contract)
  * ci/policy.yml  (dataset_scope, integration_xfail — CI-owned, not test code)

No production code is imported for its constants and none is modified. If a
dataset cannot take part, that is recorded in ci/policy.yml with a reason, so the
gap is visible in docs/ci-cd.md instead of hiding as a permanent skip.
"""

import pytest

import torch  # noqa: F401
import pyarrow  # noqa: F401

from tests.conftest import (
    DATASET_CLASSES,
    MODEL_CLASSES,
    MODEL_DATASET_CONFIGS,
    fixture_name_for,
    load_dataset_scope,
    load_known_xfails,
    offline_params,
)

_SCOPE = load_dataset_scope()
_XFAILS = load_known_xfails()

_CONFIG_IDS = sorted(MODEL_DATASET_CONFIGS)
_DATASET_IDS = sorted(DATASET_CLASSES)


def _config_cases():
    """One case per (model, dataset) config, xfail'd per ci/policy.yml."""
    cases = []
    for key in _CONFIG_IDS:
        marks = []
        if key in _XFAILS:
            marks.append(pytest.mark.xfail(reason=_XFAILS[key], strict=True))
        cases.append(pytest.param(key, marks=marks, id=key))
    return cases


# ---------------------------------------------------------------------------
# 1. Nothing discovered may be silently uncovered
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("dataset_name", _DATASET_IDS, ids=_DATASET_IDS)
def test_discovered_dataset_is_covered_or_declared_out_of_scope(dataset_name):
    """
    PASS: the dataset is reachable from some model's get_train_config(), so the
          discovery-driven suites exercise it — or ci/policy.yml declares it out
          of scope with a reason.
    FAIL: the dataset was discovered but nothing tests it and nothing explains
          why. This is the exact hole the effort exists to close: a dataset that
          is 'in the repo' and 'in CI' but contributes zero executed cases.
    """
    reachable = {cls.__name__ for _m, cls, _p, _d in MODEL_DATASET_CONFIGS.values()}

    if dataset_name in reachable:
        return

    entry = _SCOPE.get(dataset_name)
    assert entry and entry.get("reason"), (
        f"FAIL [{dataset_name}] is discovered but never exercised.\n"
        f"  → No model lists it in supported_datasets with a usable DATASET_ID, so it\n"
        f"    contributes zero test cases while CI still reports green.\n"
        f"  → Fix it in ONE of two ways:\n"
        f"      1. a model declares it (supported_datasets + DATASET_ID + get_train_config), or\n"
        f"      2. record it under 'dataset_scope' in ci/policy.yml with a reason,\n"
        f"         so the gap is published in docs/ci-cd.md instead of being invisible."
    )


@pytest.mark.parametrize("dataset_name", _DATASET_IDS, ids=_DATASET_IDS)
def test_discovered_dataset_declares_dataset_id(dataset_name):
    """
    PASS: the dataset sets DATASET_ID, which SeanergysDataset requires ("Every
          concrete dataset must set this to the key used in get_train_config()").
    FAIL: it inherits the empty default, so it can never be paired with a model
          and never enters MODEL_DATASET_PAIRS — unless ci/policy.yml records
          that this is a known gap in the dataset, owned by its author.
    """
    dataset_cls = DATASET_CLASSES[dataset_name]

    if getattr(dataset_cls, "DATASET_ID", ""):
        return

    entry = _SCOPE.get(dataset_name)
    assert entry and entry.get("reason"), (
        f"FAIL [{dataset_name}] does not set DATASET_ID.\n"
        f'  → SeanergysDataset declares `DATASET_ID: ClassVar[str] = ""` and requires\n'
        f"    every concrete dataset to set it; this one left it empty.\n"
        f"  → The dataset's author should add it. Until then, record the dataset under\n"
        f"    'dataset_scope' in ci/policy.yml so the gap is documented, not silent."
    )


def test_at_least_one_model_dataset_config_exists():
    """
    PASS: discovery produced at least one (model, dataset) configuration.
    FAIL: no model exposes a usable get_train_config(), so every config-driven
          test below would vacuously pass on an empty parameter set.
    """
    assert MODEL_DATASET_CONFIGS, (
        "No (model, dataset) configuration discovered.\n"
        f"  → Models found: {sorted(MODEL_CLASSES)}\n"
        f"  → Datasets found: {_DATASET_IDS}\n"
        "  → Check that each model sets supported_datasets and that those datasets\n"
        "    set DATASET_ID, and that get_train_config(dataset_name=...) accepts it."
    )


# ---------------------------------------------------------------------------
# 2. Every discovered configuration is well formed
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("config_key", _CONFIG_IDS, ids=_CONFIG_IDS)
def test_config_declares_features(config_key):
    """
    PASS: the model author's params name at least one input and one output
          feature, as strings.
    FAIL: the config cannot drive any dataset load, so every downstream test for
          this pair is meaningless.
    """
    _model_cls, dataset_cls, ds_params, _dl = MODEL_DATASET_CONFIGS[config_key]

    for role in ("input_features", "output_features"):
        features = getattr(ds_params, role, None)
        assert features, (
            f"FAIL [{config_key}] get_train_config() gave no {role} for "
            f"{dataset_cls.__name__}."
        )
        assert all(isinstance(f, str) and f for f in features), (
            f"FAIL [{config_key}] {role} must be column-name strings, got {features!r}."
        )


@pytest.mark.parametrize("config_key", _CONFIG_IDS, ids=_CONFIG_IDS)
def test_config_dataloader_params_are_usable(config_key):
    """
    PASS: the dataloader params carry a positive batch_size.
    FAIL: the pair cannot be batched, so the pipeline test cannot run it.
    """
    _model_cls, _dataset_cls, _ds_params, dl_params = MODEL_DATASET_CONFIGS[config_key]

    batch_size = getattr(dl_params, "batch_size", None)
    assert isinstance(batch_size, int) and batch_size > 0, (
        f"FAIL [{config_key}] dataloader batch_size is {batch_size!r}; expected a "
        f"positive int."
    )


# ---------------------------------------------------------------------------
# 3. Every discovered configuration actually loads — offline, no network
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("config_key", _config_cases())
def test_config_loads_offline_from_committed_fixture(config_key, project_root):
    """
    The payoff: build each discovered (model, dataset) pair from the model
    author's OWN config, against the committed sample fixture, with no network
    and no test-side knowledge of the dataset.

    Only the transport is overridden (local file instead of the remote source);
    features, filters and transforms are exactly what the author declared. So a
    failure here means their config does not match the real data — which is the
    class of bug that used to reach the integration job.

    PASS: the dataset instantiates offline, has rows, and dataset[0] yields (x, y).
    SKIP: no committed fixture for this dataset yet (run `make sample-data`).
    XFAIL: the pair is declared broken in ci/policy.yml -> integration_xfail.
    FAIL: the author's config cannot load the real data.
    """
    _model_cls, dataset_cls, ds_params, _dl = MODEL_DATASET_CONFIGS[config_key]

    fixture = (
        project_root
        / "tests"
        / "fixtures"
        / "sample_data"
        / fixture_name_for(dataset_cls)
    )
    if not fixture.exists():
        pytest.skip(
            f"SKIP [{config_key}] no committed fixture {fixture.name}.\n"
            f"  → Run `make sample-data` to create it."
        )

    dataset = dataset_cls(**offline_params(ds_params, fixture))

    assert len(dataset) >= 1, (
        f"FAIL [{config_key}] loaded 0 rows from {fixture.name}.\n"
        f"  → is_dummy=True must reduce the load without emptying it."
    )

    x, y = dataset[0]
    assert x is not None and y is not None, (
        f"FAIL [{config_key}] dataset[0] returned a None half."
    )


# ---------------------------------------------------------------------------
# 4. The fixture-naming rule has exactly one definition
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("dataset_name", _DATASET_IDS, ids=_DATASET_IDS)
def test_fixture_name_rule_is_shared(dataset_name):
    """
    PASS: tests/integration/conftest.py derives the fixture path from the same
          helper this test uses, so the convention cannot drift between the
          smoke suite, the integration suite and scripts/create_sample_data.py.
    FAIL: a second, divergent copy of the rule exists.
    """
    from pathlib import Path

    from tests.integration.conftest import fixture_path_for

    dataset_cls = DATASET_CLASSES[dataset_name]
    shared = fixture_name_for(dataset_cls)
    integration = fixture_path_for(dataset_cls, Path("/x")).name

    assert integration == shared, (
        f"FAIL [{dataset_name}] fixture-name rule has diverged: "
        f"integration says {integration!r}, tests/conftest.py says {shared!r}.\n"
        f"  → Both must call tests.conftest.fixture_name_for()."
    )
