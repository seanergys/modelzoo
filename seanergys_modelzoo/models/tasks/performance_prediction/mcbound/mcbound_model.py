from datetime import datetime
from typing import Any, Dict
from sklearn.ensemble import RandomForestClassifier
from pydantic import model_validator

from seanergys_modelzoo.dataloader.seanergys_dataloader import SeanergysDataloader
from seanergys_modelzoo.datasets.f_data import FDataDataset
from seanergys_modelzoo.models.common.seanergys_model import SeanergysModelTask
from seanergys_modelzoo.models.common.seanergys_model_metadata import SeanergysModelMetadata
from seanergys_modelzoo.models.common.sklearn_seanergys_model import SeanergysSklearnModel
from seanergys_modelzoo.models.tasks.performance_prediction.mcbound.functions import fit_categorical, fit_transform_categorical, transform_categorical, transform_embeddings, embedding_parsing


class MCBound(SeanergysSklearnModel):
    """
    Memory-Consumption Bound classifier.

    A RandomForestClassifier-backed classification model. All
    SeanergysSklearnModel capabilities (training, prediction,
    save/load, feature importance, probability prediction) are
    inherited without modification.

    Example usage:
        model = MCBound(model_hyperparameters={"n_estimators": 150, "max_depth": 8})
        model.train(train_loader, val_loader, validation_metrics=[accuracy_score])
        predictions = model.predict(test_loader)
        probabilities = model.predict(test_loader, return_proba=True)
        model.save("models/mcbound.joblib")
    """

    @model_validator(mode="before")
    @classmethod
    def _inject_defaults(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """
        Lock in the estimator class and task type before Pydantic validation,
        while still allowing model_hyperparameters to be customised by the caller.
        """
        values.setdefault("model_class", RandomForestClassifier)
        values.setdefault("task_type", SeanergysModelTask.CLASSIFICATION)
        values.setdefault("metadata", SeanergysModelMetadata(
                name = "MCBound", 
                created_at= datetime.now().isoformat(),
                task_type = SeanergysModelTask.CLASSIFICATION
                ))
        return values
    
    @model_validator(mode='after')
    def validate_model(self) -> 'MCBound':
        """
        Implement to validate the model
        """
        return self
    
    @classmethod
    def run_dummy_validation(cls):
        """
        Run dummy validation for MCBound on FData
        """                
        
        model_fdata = cls(model_hyperparameters={"n_jobs": -1})
        
        model_fdata.logger.info(f"Validation on FData")
        fdata = FDataDataset(use_zenodo_url=True,
                    files = "21_04",
                    transform=embedding_parsing,
                    filters=[[("adt", "<=", "2021-04-02")]],
                    input_features=["embedding"],
                    output_features=["mem_compute_bound"])
        data_loader_fdata = SeanergysDataloader(dataset = fdata, batch_size=1)
        model_fdata.train(train_data_loader=data_loader_fdata)