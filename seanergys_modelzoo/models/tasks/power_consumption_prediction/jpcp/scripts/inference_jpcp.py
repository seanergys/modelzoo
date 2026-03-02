"""
JPCP Prediction Script

Usage:
    python inference_jpcp.py --dataset fdata --start_time 2021-05-01 --end_time 2021-05-31 --model_path ../saved_model
    python inference_jpcp.py --dataset pm100 --start_time 2020-07-01 --end_time 2020-08-01 --model_path ../saved_model --output_path ../saved_model/predictions.npy
"""

import argparse
import numpy as np
import pandas as pd
from sklearn.preprocessing import LabelEncoder

from seanergys_modelzoo.dataloader.seanergys_dataloader import SeanergysDataloader
from seanergys_modelzoo.datasets.f_data import FDataDataset
from seanergys_modelzoo.datasets.pm100 import PM100Dataset
from seanergys_modelzoo.logger.seanergys_logger import SeanergysLogger
from seanergys_modelzoo.models.tasks.power_consumption_prediction.jpcp.jpcp_model import JPCP
from seanergys_modelzoo.models.tasks.power_consumption_prediction.jpcp.functions import (
    transform_categorical, embedding_parsing
)


def build_fdata_dataset(start_time: str, end_time: str) -> FDataDataset:
    """Build FDataDataset filtered between start_time and end_time."""
    return FDataDataset(
        use_zenodo_url=True,
        files="all",
        transform=embedding_parsing,
        target_transform=lambda output_features: (
            output_features[0] / output_features[1]
        ),
        filters=[[
            ("adt", ">=", start_time),
            ("adt", "<=", end_time),
        ]],
        input_features=["embedding"],
        output_features=["avgpcon", "nnuma"],
    )


def build_pm100_dataset(start_time: str, end_time: str, label_encoder:LabelEncoder) -> PM100Dataset:
    """
    Build PM100Dataset filtered between start_time and end_time.
    
    Note: Uses transform_categorical (not fit_transform_categorical) since
    the categorical encoder was already fitted during training.
    """
    return PM100Dataset(
        use_zenodo_url=True,
        transform=None,
        target_transform=lambda output_features: (
            np.mean(output_features[0]) / output_features[1]
        ),
        preprocessing_functions=[lambda features: transform_categorical(label_encoders=label_encoder, features=features)],
        filters=[[
            ("submit_time", ">=", pd.Timestamp(start_time, tz="UTC")),
            ("submit_time", "<=", pd.Timestamp(end_time, tz="UTC")),
        ]],
        columns=["num_nodes_req", "user_id", "node_power_consumption", "num_nodes_alloc"],
        input_features=["num_nodes_req_cat", "user_id_cat"],
        output_features=["node_power_consumption", "num_nodes_alloc"],
    )


def main():
    parser = argparse.ArgumentParser(description="Run inference with a trained JPCP model.")
    parser.add_argument(
        "--dataset",
        choices=["fdata", "pm100"],
        required=True,
        help="Dataset to predict on: 'fdata' or 'pm100'.",
    )
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
        help="Path to the saved model .joblib file produced by train_jpcp.py.",
    )
    parser.add_argument(
        "--output_path",
        default=None,
        help="Path to save predictions as a .npy file.",
    )
    args = parser.parse_args()
    
    logger = SeanergysLogger()

    logger.info(f"Loading model from {args.model_path}...")
    model = JPCP.load(args.model_path)

    logger.info(f"Building {args.dataset.upper()} dataset [{args.start_time} → {args.end_time}]...")
    if args.dataset == "fdata":
        dataset = build_fdata_dataset(args.start_time, args.end_time)
    else:
        dataset = build_pm100_dataset(args.start_time, args.end_time)

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