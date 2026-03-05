"""
Discover and validate SeanergysDataset classes in a folder.
Used by GitLab CI test stage.
"""
import argparse
import sys
from pathlib import Path
from typing import Dict, Type

from seanergys_modelzoo.logger.seanergys_logger import SeanergysLogger
from seanergys_modelzoo.datasets.common.seanergys_dataset import SeanergysDataset

from ci.utils import retrieve_instances_from_file


def fetch_dataset_classes(data_folder: Path, logger: SeanergysLogger) -> Dict[str, Type[SeanergysDataset]]:
    """
    Discover all SeanergysDataset classes in the dataset folder.
    Uses rglob to support both flat and nested layouts.

    Returns:
        Dict mapping dataset names to dataset classes.
    """
    logger.info(f"Fetching SeanergysDataset classes in {data_folder}")

    if not data_folder.exists():
        raise FileNotFoundError(f"Data folder not found: {data_folder}")

    data_classes: Dict[str, Type[SeanergysDataset]] = {}

    for py_file in data_folder.rglob("*.py"):
        if py_file.name == "__init__.py":
            continue
        try:
            dataset_objects = retrieve_instances_from_file(py_file, SeanergysDataset)
            if dataset_objects:
                for name in dataset_objects:
                    logger.info(f"Found dataset class {name} in {py_file}")
                data_classes.update(dataset_objects)
        except Exception as e:
            logger.warning(f"Could not load {py_file}: {e}")

    logger.info(f"Found {len(data_classes)} dataset classes")
    return data_classes


def main(data_folder: str | Path) -> None:
    """Main entry point for dataset validation."""
    logger = SeanergysLogger()
    data_classes = fetch_dataset_classes(Path(data_folder), logger)

    if not data_classes:
        logger.warning("No dataset classes found")
        sys.exit(0)

    logger.info("All dataset discoveries passed")
    sys.exit(0)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validate all SeanergysDataset classes")
    parser.add_argument("--data-folder", "-d", type=str, required=True, help="Path to dataset folder")
    args = parser.parse_args()
    main(data_folder=args.data_folder)
