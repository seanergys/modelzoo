from datetime import datetime
import time
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple, Type, Union
from sklearn.ensemble import RandomForestRegressor
from pydantic import Field, model_validator
from enum import Enum
import numpy as np
import pandas as pd

from seanergys_modelzoo.dataloader.seanergys_dataloader import SeanergysDataloader
from seanergys_modelzoo.datasets.common.seanergys_dataset import SeanergysDataset
from seanergys_modelzoo.datasets.f_data import FDataDataset
from seanergys_modelzoo.datasets.pm100 import PM100Dataset
from seanergys_modelzoo.models.common.seanergys_configurator import SeanergysDataloaderParams, SeanergysDatasetParams, SeanergysModelParams
from seanergys_modelzoo.models.common.seanergys_model import SeanergysModelTask
from seanergys_modelzoo.models.common.seanergys_model_metadata import SeanergysModelMetadata
from seanergys_modelzoo.models.common.sklearn_seanergys_model import SeanergysSklearnModel
from seanergys_modelzoo.models.tasks.power_consumption_prediction.jpcp.functions import fit_categorical, fit_transform_categorical, transform_categorical, transform_embeddings, embedding_parsing

class Embedding(Enum):
    INT = 0 # Input features are mapped to categorical 
    SB = 1 # Input features are encoded with sentence_transformers
    NONE = 2 # Input features are used as is


class JPCP(SeanergysSklearnModel):
    """
    Job Power Consumption Predictor.

    A RandomForestRegressor-backed regression model that predicts the power
    consumption of HPC jobs. All SeanergysSklearnModel capabilities
    (training, prediction, save/load, feature importance) are inherited
    without modification.

    Example usage:
        model = JPCP(model_hyperparameters={"n_estimators": 200, "max_depth": 10})
        model.train(train_loader, val_loader, validation_metrics=[mean_absolute_error])
        predictions = model.predict(test_loader)
        model.save("models/jpcp.joblib")
    """    
    
    @model_validator(mode="before")
    @classmethod
    def _inject_defaults(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """
        Lock in the estimator class and task type before Pydantic validation,
        while still allowing model_hyperparameters to be customised by the caller.
        """
        values.setdefault("model_class", RandomForestRegressor)
        values.setdefault("task_type", SeanergysModelTask.REGRESSION)
        values.setdefault("supported_datasets", [PM100Dataset, FDataDataset])
        values.setdefault("metadata", SeanergysModelMetadata(
                name = "JPCP", 
                created_at= datetime.now().isoformat(),
                task_type = SeanergysModelTask.REGRESSION
                ))
        
        return values
    
    @model_validator(mode='after')
    def validate_model(self) -> 'JPCP':
        """
        Implement to validate the model
        """
        return self
                            
    @classmethod
    def run_dummy_validation(cls):
        """
        Run dummy validation for JPCP.

        """                
        
        model_fdata = cls(model_hyperparameters={"n_jobs": -1})
        
        model_fdata.logger.info(f"Validation on FData")
        fdata = FDataDataset(use_zenodo_url=True,
                    files = "21_04",
                    transform=embedding_parsing,
                    target_transform=lambda output_features: (
                        output_features[0] / output_features[1]
                    ),
                    filters=[[("adt", "<=", "2021-04-02")]],
                    input_features=["embedding"],
                    output_features=["avgpcon", "nnuma"])
        data_loader_fdata = SeanergysDataloader(dataset = fdata, batch_size=1)
        model_fdata.train(train_data_loader=data_loader_fdata)
        
        model_pm100 = cls(model_hyperparameters={"n_jobs": -1})
        model_pm100.logger.info(f"Validation on PM100")
        pm100 = PM100Dataset(
            use_zenodo_url=True,
            transform=None,
            target_transform=lambda output_features: (
                np.mean(output_features[0]) / output_features[1]
            ),
            preprocessing_functions=[
                fit_transform_categorical
                
            ],
            filters=[[("submit_time", "<=", pd.Timestamp("2020-07-01", tz = "UTC"))]],
            columns=["num_nodes_req", "user_id", "node_power_consumption", "num_nodes_alloc"],
            input_features=["num_nodes_req_cat", "user_id_cat"],
            output_features=["node_power_consumption", "num_nodes_alloc"],
            )
        data_loader_pm100 = SeanergysDataloader(dataset = pm100, batch_size=1)
        model_pm100.train(train_data_loader=data_loader_pm100)

    