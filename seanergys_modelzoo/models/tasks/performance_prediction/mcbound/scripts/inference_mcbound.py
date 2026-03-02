"""
MCBound Prediction Script

Usage:
    python inference_mcbound.py --start_time 2021-05-01 --end_time 2021-05-31 --model_path ../saved_model
    python inference_mcbound.py --start_time 2020-07-01 --end_time 2020-08-01 --model_path ../saved_model --output_path ../saved_model/predictions.npy
"""

import argparse
import numpy as np
import pandas as pd
from sklearn.preprocessing import LabelEncoder

from seanergys_modelzoo.dataloader.seanergys_dataloader import SeanergysDataloader
from seanergys_modelzoo.datasets.f_data import FDataDataset
from seanergys_modelzoo.datasets.pm100 import PM100Dataset
from seanergys_modelzoo.logger.seanergys_logger import SeanergysLogger
from seanergys_modelzoo.models.tasks.performance_prediction.mcbound.mcbound_model import MCBound
from seanergys_modelzoo.models.tasks.performance_prediction.mcbound.functions import embedding_parsing



def build_fdata_dataset(start_time: str, end_time: str) -> FDataDataset:
    """Build FDataDataset filtered between start_time and end_time."""
    return FDataDataset(
        use_zenodo_url=True,
        files = "all",
        transform=embedding_parsing,
        filters=[[
            ("adt", ">=", start_time),
            ("adt", "<=", end_time),
        ]],
        input_features=["embedding"],
        output_features=["mem_compute_bound"]
        )
    
    
def main():
    parser = argparse.ArgumentParser(description="Run inference with a trained MCBound model.")
    parser.add_argument(
        "--start_time",
        required=True,
        help="Start time filter (e.g. 2021-05-01). Inclusive.",
    )
    parser.add_argument(
        "--end_time",
        required=True,
        help="End time filter (e.g. 2021-05-31). Inclusive.",
    )
    parser.add_argument(
        "--model_path",
        required=True,
        help="Path to the saved model .joblib file produced by train_mcbound.py.",
    )
    parser.add_argument(
        "--output_path",
        default=None,
        help="Path to save predictions as a .npy file.",
    )
    args = parser.parse_args()
    
    logger = SeanergysLogger()

    logger.info(f"Loading model from {args.model_path}...")
    model = MCBound.load(args.model_path)

    logger.info(f"Building {args.dataset.upper()} dataset [{args.start_time} → {args.end_time}]...")
    dataset = build_fdata_dataset(args.start_time, args.end_time)

    data_loader = SeanergysDataloader(dataset=dataset, batch_size=1)

    logger.info("Running predictions...")
    predictions = model.predict(data_loader)

    logger.info(f"Generated {len(predictions)} predictions.")

    if args.output_path:
        np.save(args.output_path, predictions)
        logger.info(f"Predictions saved to {args.output_path}.")
    
    # Output predictions
    logger.info(f"Predictions:\n{predictions}\n")

if __name__ == "__main__":
    main()