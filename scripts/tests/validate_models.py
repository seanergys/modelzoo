"""
This script automatically loads SeanergysModel classesfrom specified
folders, then runs validation for all combinations specified in configuration files.
"""

import argparse
import sys
import os
from pathlib import Path
from typing import Dict, List, Tuple, Type, Any

from seanergys_modelzoo.dataloader.seanergys_dataloader import SeanergysDataloader
from seanergys_modelzoo.logger.seanergys_logger import SeanergysLogger
from seanergys_modelzoo.datasets.common.seanergys_dataset import SeanergysDataset
from seanergys_modelzoo.models.common.seanergys_configurator import SeanergysModelConfiguration
from seanergys_modelzoo.models.common.seanergys_model import SeanergysModel
from tests.seanergys_model_evaluator import SeanergysModelEvaluator
from scripts.utils import retrieve_instances_from_file

def fetch_model_classes_and_config(model_folder:Path, logger:SeanergysLogger) -> Dict[str, SeanergysModel]:
    """
    Fetch all SeanergysModel classes in the model folder.
    
    Returns:
        Dictionary mapping model names to SeanergysModel classes
    """    
    logger.info(f"Fetching SeanergysModel classes in {model_folder}")
    
    if not model_folder.exists():
        raise FileNotFoundError(f"Model folder not found: {model_folder}")
    
    model_classes = {}
    
    # Fetch all the files in the base dir
    for py_file in model_folder.rglob("*.py"):        
        # Fetch model classes
        model_objects = retrieve_instances_from_file(py_file, SeanergysModel)
        if len(model_objects):
            logger.info(f"Found {','.join(model_objects.keys())} model classes in {py_file}")
        model_classes.update(model_objects)
        
    logger.info(f"Found {len(model_classes)} model classes")
    return model_classes

def main(model_folder:str | Path, run_dummy:bool = False):
    """Main entry point for the validation runner script."""
    
    logger = SeanergysLogger()
            
    model_classes = fetch_model_classes_and_config(model_folder=Path(model_folder), logger=logger)
            
    # Run dummy evaluation
    for _, model_class in model_classes.items():
        train_configs = model_class.get_train_config()
        for model_instance, dataset, data_configs in train_configs.items():
            logger.info(f"Validating {model_instance.model_name} on {dataset}")
            dataset_config, dataloader_config = data_configs
            dataset_config.is_dummy = True
            dataset = dataset.from_config(dataset_config)
            dataloader_instance = SeanergysDataloader.from_config(data_loader_config=dataloader_config, dataset=dataset)
            model_instance.train(dataloader_instance)
          
    
    # Exit with appropriate code
    logger.info("Test terminated with no errors")
    sys.exit(0)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Validate all the SeanergysModel classes"
    )
    
    parser.add_argument(
        '--model-folder',
        '--m',
        type=str,
        required=True,
        help='Path to folder containing model classes'
    )
        
    args = parser.parse_args()
    
    model_folder = args.model_folder
    
    main(model_folder=model_folder)