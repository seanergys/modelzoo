"""
This script automatically loads SeanergysModel classes and SeanergysDataset classes from specified
folders, then runs validation for all combinations specified in configuration files.
"""

import argparse
import sys
import os
from pathlib import Path
from typing import Dict, List, Tuple, Type, Any

from seanergys_modelzoo.logger.seanergys_logger import SeanergysLogger
from seanergys_modelzoo.datasets.common.seanergys_dataset import SeanergysDataset
from scripts.utils import import_module_from_file, retrieve_instances_from_file
    
def fetch_dataset_classes_and_config(data_folder:Path, logger:SeanergysLogger) -> Dict[str, SeanergysDataset]:
    """
    Fetch all SeanergysDataset classes in the dataset folder.
    
    Returns:
        Dictionary mapping data names to SeanergysDataset classes
    """    
    logger.info(f"Fetching SeanergysDataset classes in {data_folder}")
    
    if not data_folder.exists():
        raise FileNotFoundError(f"Model folder not found: {data_folder}")
    
    data_classes = {}
        
    # For each task extract the models
    for dataset in os.listdir(os.path.join(data_folder)):
        dataset_folder = os.path.join(data_folder, dataset)
        if not(os.path.isdir(dataset_folder)):
            continue                
        
        # Fetch data file
        try:
            data_file = next(Path(dataset_folder).rglob("*.py"))
            data_objects = retrieve_instances_from_file(data_file, SeanergysDataset)
            for name in data_objects:
                logger.info(f"Found data class {name} in {data_file}")
            data_classes.update(data_objects)
        except:
            raise Exception(f"Dataset file for model {dataset} not found in {data_folder}")
    
    logger.info(f"Fetched {len(data_classes)} model classes")
    return data_classes

def main(data_folder = str | Path):
    """Main entry point for the validation runner script."""
    
                
    logger = SeanergysLogger()
            
    data_classes = fetch_dataset_classes_and_config(data_folder=Path(data_folder), logger=logger)
            
    # Exit with appropriate code
    logger.info("Test terminated with no errors")
    sys.exit(0)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Validate all the SeanergysDataset classes"
    )
    
    parser.add_argument(
        '--data-folder',
        '--d',
        type=str,
        required=True,
        help='Path to folder containing dataset classes'
    )
    
    args = parser.parse_args()
    
    data_folder = args.data_folder
    
    main(data_folder=data_folder)