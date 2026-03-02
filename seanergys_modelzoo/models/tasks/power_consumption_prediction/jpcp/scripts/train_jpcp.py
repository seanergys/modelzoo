"""
JPCP Training Script

Usage:
    python train_jpcp.py --dataset fdata --start_time 2021-04-01 --end_time 2021-04-30 --output_path ../saved_model
    python train_jpcp.py --dataset pm100 --start_time 2020-05-01 --end_time 2020-07-01 --output_path ../saved_model
"""

import argparse
import numpy as np
import pandas as pd

from seanergys_modelzoo.dataloader.seanergys_dataloader import SeanergysDataloader
from seanergys_modelzoo.datasets.f_data import FDataDataset
from seanergys_modelzoo.datasets.pm100 import PM100Dataset
from seanergys_modelzoo.logger.seanergys_logger import SeanergysLogger
from seanergys_modelzoo.models.tasks.power_consumption_prediction.jpcp.jpcp_model import JPCP
from seanergys_modelzoo.models.tasks.power_consumption_prediction.jpcp.functions import (
    fit_transform_categorical, embedding_parsing
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


def build_pm100_dataset(start_time: str, end_time: str) -> PM100Dataset:
    """Build PM100Dataset filtered between start_time and end_time."""
    return PM100Dataset(
        use_zenodo_url=True,
        transform=None,
        target_transform=lambda output_features: (
            np.mean(output_features[0]) / output_features[1]
        ),
        preprocessing_functions=[fit_transform_categorical],
        filters=[[
            ("submit_time", ">=", pd.Timestamp(start_time, tz="UTC")),
            ("submit_time", "<=", pd.Timestamp(end_time, tz="UTC")),
        ]],
        columns=["num_nodes_req", "user_id", "node_power_consumption", "num_nodes_alloc"],
        input_features=["num_nodes_req_cat", "user_id_cat"],
        output_features=["node_power_consumption", "num_nodes_alloc"],
    )


def main():
    parser = argparse.ArgumentParser(description="Train the JPCP model.")
    parser.add_argument(
        "--dataset",
        choices=["fdata", "pm100"],
        required=True,
        help="Dataset to train on: 'fdata' or 'pm100'.",
    )
    parser.add_argument(
        "--start_time",
        required=True,
        help="Start time filter (e.g. 2021-04-01). Inclusive.",
    )
    parser.add_argument(
        "--end_time",
        required=True,
        help="End time filter (e.g. 2021-04-30). Inclusive.",
    )
    parser.add_argument(
        "--output_path",
        default="../saved_model",
        help="Path to save the trained model (default: ../saved_model).",
    )
    
    args = parser.parse_args()
    
    logger = SeanergysLogger()

    logger.info(f"Building {args.dataset.upper()} dataset [{args.start_time} → {args.end_time}]...")

    if args.dataset == "fdata":
        dataset = build_fdata_dataset(args.start_time, args.end_time)
    else:
        dataset = build_pm100_dataset(args.start_time, args.end_time)

    data_loader = SeanergysDataloader(dataset=dataset, batch_size=1)

    logger.info("Initialising JPCP model...")
    model = JPCP(model_hyperparameters={"n_jobs": args.n_jobs})

    logger.info("Training...")
    history = model.train(train_data_loader=data_loader)
    logger.info(f"Training complete. History: {history}")

    logger.info(f"Saving model to {args.output_path}...")
    model.save(args.output_path)
    logger.info("Done.")


if __name__ == "__main__":
    main()