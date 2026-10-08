from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Callable, ClassVar, Dict, List, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field


class SeanergysComponentsParams(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="allow")

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SeanergysComponentsParams":
        return cls(**data)


class SeanergysModelParams(SeanergysComponentsParams):
    pass


class SeanergysDatasetParams(SeanergysComponentsParams):
    data_path: Optional[Path] = Field(default=None)
    transform: Optional[Callable] = Field(default=None)
    target_transform: Optional[Callable] = Field(default=None)
    metadata: Optional[Any] = Field(default=None)

    def to_dict(self) -> Dict[str, Any]:
        result = {}
        for key, value in self.model_dump().items():
            if value is not None:
                result[key] = value
        for key in self.model_fields_set:
            if key not in result:
                result[key] = getattr(self, key)
        extra = self.model_extra or {}
        result.update(extra)
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SeanergysDatasetParams":
        return cls(**data)


class SeanergysDataloaderParams(SeanergysComponentsParams):
    batch_size: Optional[int] = Field(default=1)
    shuffle: Optional[bool] = Field(default=None)
    sampler: Optional[Any] = Field(default=None)
    batch_sampler: Optional[Any] = Field(default=None)
    num_workers: int = Field(default=0)
    collate_fn: Optional[Callable] = Field(default=None)
    pin_memory: bool = Field(default=False)
    drop_last: bool = Field(default=False)
    timeout: float = Field(default=0)
    worker_init_fn: Optional[Callable] = Field(default=None)
    multiprocessing_context: Optional[Any] = Field(default=None)
    generator: Optional[Any] = Field(default=None)
    prefetch_factor: Optional[int] = Field(default=None)
    persistent_workers: bool = Field(default=False)
    pin_memory_device: str = Field(default="")
    in_order: bool = Field(default=True)

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SeanergysDataloaderParams":
        return cls(**data)

# class SeanergysModelConfiguration(BaseModel, ABC):
#     """
#     Abstract configurator that binds a SeanergysModel to one or more
#     SeanergysDatasets via fully typed parameter bundles.

#     For each concrete SeanergysModel, create one subclass of this class and
#     implement get_training_params, get_testing_params, and get_validation_params
#     for every dataset the model supports.
#     """

#     model_config = ConfigDict(arbitrary_types_allowed=True)

#     # ClassVar (not a Pydantic field): subclasses override it at the class
#     # level and pipeline code reads it without instantiating the configurator.
#     SUPPORTED_DATASETS: ClassVar[List[Any]] = []

#     # Declare MODEL_CLASS in every concrete subclass so the pipeline engine can
#     # auto-discover and register model+config pairs without manual wiring.
#     MODEL_CLASS: ClassVar[Any] = None

#     @classmethod
#     @abstractmethod
#     def get_dummy_params(
#         cls, dataset: Any
#     ) -> Tuple[SeanergysModelParams, SeanergysDatasetParams, SeanergysDataloaderParams]:
#         """Return the full parameter bundle for dummy testing on the given dataset."""
#         pass

#     @classmethod
#     @abstractmethod
#     def get_training_params(
#         cls, dataset: Any
#     ) -> Tuple[SeanergysModelParams, SeanergysDatasetParams, SeanergysDataloaderParams]:
#         """Return the full parameter bundle for training on the given dataset."""
#         pass

#     @classmethod
#     @abstractmethod
#     def get_testing_params(
#         cls, dataset: Any
#     ) -> Tuple[SeanergysModelParams, SeanergysDatasetParams, SeanergysDataloaderParams]:
#         """Return the full parameter bundle for testing on the given dataset."""
#         pass

#     @classmethod
#     @abstractmethod
#     def get_validation_params(
#         cls, dataset: Any
#     ) -> Tuple[SeanergysModelParams, SeanergysDatasetParams, SeanergysDataloaderParams]:
#         """Return the full parameter bundle for validation on the given dataset."""
#         pass

#     @classmethod
#     def get_dataset_classes(cls) -> List:
#         """Return the list of dataset classes this configuration supports."""
#         return cls.SUPPORTED_DATASETS