"""
Discover and validate SeanergysModel classes in a folder.
Used by GitLab CI test stage.
"""
import argparse
import sys
from pathlib import Path
from typing import Dict, Type

from seanergys_modelzoo.logger.seanergys_logger import SeanergysLogger
from seanergys_modelzoo.models.common.seanergys_model import SeanergysModel

from ci.utils import retrieve_instances_from_file


def fetch_model_classes(model_folder: Path, logger: SeanergysLogger) -> Dict[str, Type[SeanergysModel]]:
    """
    Discover all SeanergysModel classes in the model folder.

    Returns:
        Dict mapping model names to model classes.
    """
    logger.info(f"Fetching SeanergysModel classes in {model_folder}")

    if not model_folder.exists():
        raise FileNotFoundError(f"Model folder not found: {model_folder}")

    model_classes: Dict[str, Type[SeanergysModel]] = {}

    for py_file in model_folder.rglob("*.py"):
        model_objects = retrieve_instances_from_file(py_file, SeanergysModel)
        if model_objects:
            logger.info(f"Found {','.join(model_objects.keys())} in {py_file}")
            model_classes.update(model_objects)

    logger.info(f"Found {len(model_classes)} model classes")
    return model_classes


def main(model_folder: str | Path, run_dummy: bool = True) -> None:
    """Main entry point for model validation."""
    logger = SeanergysLogger()
    model_classes = fetch_model_classes(Path(model_folder), logger)

    if not run_dummy:
        logger.info("Skipping dummy validation (discovery only)")
        sys.exit(0)

    for name, model_class in model_classes.items():
        try:
            logger.info(f"Validating {name}...")
            model_class.run_dummy_validation()
        except Exception as e:
            logger.error(f"Validation failed for {name}: {e}")
            sys.exit(1)

    logger.info("All model validations passed")
    sys.exit(0)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validate all SeanergysModel classes")
    parser.add_argument("--model-folder", "-m", type=str, required=True, help="Path to model folder")
    parser.add_argument(
        "--no-dummy",
        action="store_true",
        help="Skip dummy validation (discovery only)",
    )
    args = parser.parse_args()

    run_dummy = not args.no_dummy
    main(model_folder=args.model_folder, run_dummy=run_dummy)
