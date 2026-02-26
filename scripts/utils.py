import importlib
import inspect
from pathlib import Path
import sys
from typing import Any, Type


def import_module_from_file(file_path: Path) -> Any:
    """
    Dynamically import a Python module from a file path.
    
    Args:
        file_path: Path to the Python file
        
    Returns:
        Imported module object
    """
    spec = importlib.util.spec_from_file_location(file_path.stem, file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module from {file_path}")
    
    module = importlib.util.module_from_spec(spec)
    sys.modules[file_path.stem] = module
    spec.loader.exec_module(module)
    return module

def retrieve_instances_from_file(file_path: Path, class_type:Type) -> Type:
    instances = {}
    
    module = import_module_from_file(file_path)
    # print(module.__dict__)
            
    # Find all classes in the module
    for name, obj in inspect.getmembers(module, inspect.isclass):
        # Check if class is instance of class_type
        # print(obj.__module__)
        if issubclass(obj, class_type) and obj.__module__ == module.__name__:
            instances[name] = obj
    
    return instances   