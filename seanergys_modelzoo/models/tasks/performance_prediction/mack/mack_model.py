from datetime import datetime
import os
from pathlib import Path
import pickle
import joblib
from typing import Any, Dict, Iterable, List, Optional, Union
from seanergys_modelzoo.dataloader.seanergys_dataloader import SeanergysDataloader
from seanergys_modelzoo.datasets.f_data import FDataDataset
from seanergys_modelzoo.models.common.seanergys_model import SeanergysModelTask
from seanergys_modelzoo.models.common.seanergys_model_metadata import SeanergysModelMetadata
from xgboost import XGBClassifier
from sklearn.cluster import KMeans
from sentence_transformers import SentenceTransformer
import numpy as np
from pydantic import model_validator, Field

from seanergys_modelzoo.models.common.sklearn_seanergys_model import SeanergysSklearnModel
from seanergys_modelzoo.models.tasks.performance_prediction.mack.functions import fit_transform_kmeans, transform_embeddings, embedding_parsing

class MACK(SeanergysSklearnModel):
    """
    Class for the MACK framework
    """
    
    kmeans_flops: Optional[KMeans] = Field(default = None, description = "The fitted kmeans to cluster the flops values")
    kmeans_memory_bw: Optional[KMeans] = Field(default = None, description = "The fitted kmeans to cluster the memory bandwidth values")
    
            
    @model_validator(mode="before")
    @classmethod
    def _inject_defaults(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """
        Lock in the estimator class and task type before Pydantic validation,
        while still allowing model_hyperparameters to be customised by the caller.
        """
        values.setdefault("model_class", XGBClassifier)
        values.setdefault("task_type", SeanergysModelTask.CLASSIFICATION)
        values.setdefault("metadata", SeanergysModelMetadata(
                name = "MACK", 
                created_at= datetime.now().isoformat(),
                task_type = SeanergysModelTask.CLASSIFICATION
                ))
        return values
    
    @model_validator(mode='after')
    def validate_model(self) -> 'MACK':
        """
        Implement to validate the model
        """
        return self
    
    @classmethod
    def run_dummy_validation(cls):
        """
        Run dummy validation for MACK on FData
        """                
        
        model_fdata = cls(model_hyperparameters={"n_jobs": -1})
        model_fdata.logger.info(f"Validation on FData")
        
        # Define pclass creation
        def preprocess_fdata(df):
            df["pclass"] = fit_transform_kmeans(df.flops.values, df.memory_bw.values, 2, 2)
            return df
        
        fdata = FDataDataset(use_zenodo_url=True,
                    files = "21_04",
                    transform=embedding_parsing,
                    preprocessing_functions = [preprocess_fdata],
                    filters=[[("adt", "<=", "2021-04-02")]],
                    input_features=["embedding"],
                    output_features=["mem_compute_bound"])
        data_loader_fdata = SeanergysDataloader(dataset = fdata, batch_size=1)
        model_fdata.train(train_data_loader=data_loader_fdata)
        

    def save(
        self,
        path: Union[str, Path] = "./saved_model",
        compress: int = 3,
        **kwargs
    ) -> bool:
        """
        Persist the estimator, kmeans, metadata, and supplementary info to disk.

        Args:
            path:     Destination path for the joblib model file.
            compress: joblib compression level (0–9).

        Returns:
            True on success, False on failure.
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            # Save the kmeans
            joblib.dump(self.kmeans_flops, f"{os.path.join(str(path), 'kmeans_flops.joblib')}", compress = compress)
            self.logger.info(f"Kmeans flops saved to {path}")
            
            joblib.dump(self.kmeans_memory_bw, f"{os.path.join(str(path), 'kmeans_memory_bw.joblib')}", compress = compress)
            self.logger.info(f"Kmeans memory_bw saved to {path}")
            
            super().save(path=path, compress=compress)
        
        except Exception as e:
            self.logger.error(f"Error saving model: {e}")
            return False

    @classmethod
    def load(
        cls,
        path: Union[str, Path] = "./saved_model",
        **kwargs
    ) -> "MACK":
        """
        Restore a MACK model from disk.

        Args:
            path: Path to the joblib model file produced by save().

        Returns:
            A fully restored MACK instance.
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Model file not found: {path}")

        try:
            obj = super().load(path=path, **kwargs)
            obj.kmeans_flops = joblib.load(f"{os.path.join(str(path), 'kmeans_flops.joblib')}")
            obj.kmeans_memory_bw = joblib.load(f"{os.path.join(str(path), 'kmeans_memory_bw.joblib')}")
            return obj

        except Exception as e:
            raise RuntimeError(f"Error loading model: {e}") from e