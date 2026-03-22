#!/usr/bin/env python3
"""
Create small sample fixture files for local testing and CI.

WHY THIS FILE EXISTS
--------------------
Francesco's original CI scripts ran validation directly against Zenodo —
every test run downloaded the full dataset. That made CI slow, fragile
(network-dependent), and impossible to run offline.

This script solves that by downloading a tiny sample ONCE (during CI setup or
locally with `make sample-data`) and saving it as a local parquet file.
The integration tests then use those local files — no network needed during
the actual test run.

HOW IT WORKS
------------
Instead of hardcoding dataset names or requiring get_dummy_params(), this script
uses the models as the entry point:

  1. Auto-discover every SeanergysModel subclass in models/tasks/
  2. Call get_train_config() on each — this already defines which dataset class
     to use, which input/output features, and which filters
  3. Override ds_params with is_dummy=True to get a small filtered subset
  4. Instantiate the dataset — the model_validator fires load_data() automatically
  5. Save the loaded DataFrame to tests/fixtures/sample_data/

Datasets are deduplicated — if MACK and MCBound both use FDataDataset, it is
only downloaded once.

When a developer adds a new model with get_train_config(), its dataset fixture
is created automatically — no changes needed here.

LIMITATION
----------
If a dataset is added without any model (no get_train_config() pointing to it),
this script will not create a fixture for it. In that case, get_dummy_params()
must be implemented on the dataset class — see docs/COLLEAGUE_FEEDBACK.md §6.1.

Usage:
    python scripts/create_sample_data.py
    SAMPLE_MAX_ROWS=50 python scripts/create_sample_data.py
    python scripts/create_sample_data.py --max-rows 200

Output:
    tests/fixtures/sample_data/sample_<datasetclassname_lower>.parquet
"""

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _max_rows() -> int:
    return int(os.environ.get("SAMPLE_MAX_ROWS", os.environ.get("CI_MAX_SAMPLES", "100")))


def _output_dir() -> Path:
    d = PROJECT_ROOT / "tests" / "fixtures" / "sample_data"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _discover_model_classes() -> dict:
    """
    Auto-discover all concrete SeanergysModel subclasses in models/tasks/.
    Same mechanism as tests/conftest.py — no model names hardcoded.
    """
    try:
        from ci.utils import retrieve_instances_from_file
        from seanergys_modelzoo.models.common.seanergys_model import SeanergysModel
    except ImportError as e:
        print(f"Cannot import project packages: {e}", file=sys.stderr)
        sys.exit(1)

    classes = {}
    for py_file in (PROJECT_ROOT / "seanergys_modelzoo" / "models" / "tasks").rglob("*.py"):
        if py_file.name == "__init__.py":
            continue
        try:
            classes.update(retrieve_instances_from_file(py_file, SeanergysModel))
        except Exception:
            continue
    return classes


def _collect_dataset_configs(model_classes: dict) -> dict:
    """
    Call get_train_config() on every model and collect unique datasets.

    Returns a dict of {dataset_class_name: (dataset_cls, ds_params)} —
    deduplicated so the same dataset is not downloaded multiple times even
    if multiple models use it.
    """
    seen = {}

    for model_name, model_cls in model_classes.items():
        try:
            config = model_cls.get_train_config()
        except Exception as e:
            print(f"  WARN  {model_name}.get_train_config() failed: {e}")
            continue

        for entry_name, (model_instance, dataset_cls, (ds_params, dl_params)) in config.items():
            key = dataset_cls.__name__
            if key not in seen:
                seen[key] = (dataset_cls, ds_params)
                print(f"  found {key} (via {model_name}/{entry_name})")

    return seen


def create_sample(dataset_cls, ds_params, max_rows: int, out_dir: Path) -> Path:
    """
    Download a small sample from Zenodo and save to parquet.

    WHY WE DO NOT USE is_dummy=True HERE
    --------------------------------------
    Francesco's is_dummy=True implementation is currently broken:
      - FDataDataset: appends a tuple to a list-of-lists filter → invalid pyarrow
        predicate format. Also uses "21-04" (hyphen) instead of "21_04" (underscore).
      - These are documented in docs/COLLEAGUE_FEEDBACK.md §6.3.

    Instead we use only the essential params from get_train_config() — just
    input_features, output_features, and use_zenodo_url=True — and override
    `files` to a single month to keep the download small. No transforms, no
    preprocessing, no filters. We then take head(max_rows) after loading.

    WHY WE STRIP TRANSFORMS AND PREPROCESSING
    ------------------------------------------
    Some models (e.g. MACK) define transforms that require a fitted model
    (e.g. embedding_parsing, transform_kmeans). These cannot run at sample
    creation time — the model has not been trained yet. Raw column values
    are sufficient for fixture files; the integration tests load data
    and apply transforms at training time.
    """
    # Build minimal safe params — only what is needed to download raw data
    essential_params = {
        "input_features": ds_params.input_features,
        "output_features": ds_params.output_features,
        "use_zenodo_url": True,
    }

    # If the dataset supports a `files` field (e.g. FDataDataset loads monthly
    # parquet files), load only the first available file instead of all 38.
    if hasattr(dataset_cls, "AVAILABLE_FILES") and dataset_cls.AVAILABLE_FILES:
        essential_params["files"] = dataset_cls.AVAILABLE_FILES[0]

    # Instantiate — model_validator fires load_data() automatically
    dataset = dataset_cls(**essential_params)

    df = dataset._df.head(max_rows)

    # Consistent naming: FDataDataset → sample_fdata.parquet
    name = dataset_cls.__name__.lower().replace("dataset", "")
    out_path = out_dir / f"sample_{name}.parquet"
    df.to_parquet(out_path, index=False)

    return out_path


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Create sample fixture parquet files using model get_train_config()."
    )
    parser.add_argument(
        "--max-rows",
        type=int,
        default=None,
        help="Max rows per sample (default: SAMPLE_MAX_ROWS or CI_MAX_SAMPLES or 100).",
    )
    args = parser.parse_args()

    max_rows = args.max_rows or _max_rows()
    out_dir = _output_dir()

    print("Discovering models...")
    model_classes = _discover_model_classes()
    if not model_classes:
        print("No model classes found.")
        sys.exit(1)
    print(f"Found {len(model_classes)} model(s): {', '.join(model_classes)}\n")

    print("Collecting datasets from get_train_config()...")
    dataset_configs = _collect_dataset_configs(model_classes)
    if not dataset_configs:
        print("No datasets found via get_train_config().")
        sys.exit(1)
    print(f"\nWill create samples for: {', '.join(dataset_configs)}")
    print(f"Output dir : {out_dir}")
    print(f"Max rows   : {max_rows}\n")

    errors = []
    for dataset_name, (dataset_cls, ds_params) in dataset_configs.items():
        try:
            print(f"  ...   {dataset_name}")
            out_path = create_sample(dataset_cls, ds_params, max_rows=max_rows, out_dir=out_dir)
            print(f"  OK    {dataset_name} → {out_path.name}")
        except Exception as e:
            print(f"  ERR   {dataset_name}: {e}")
            errors.append(dataset_name)

    print()
    if errors:
        print(
            f"WARNING: {len(errors)} dataset(s) could not be sampled and were skipped: "
            f"{', '.join(errors)}\n"
            "Other fixtures were created successfully. Fix the errors above and re-run "
            "`make sample-data` to fill in the missing ones.",
            file=sys.stderr,
        )
    succeeded = len(dataset_configs) - len(errors)
    print(f"Done. {succeeded}/{len(dataset_configs)} fixture(s) created.")


if __name__ == "__main__":
    main()
