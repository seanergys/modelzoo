#!/usr/bin/env python3
"""
Verify the *installed* seanergys_modelzoo wheel imports correctly.

Run this in the test-wheel CI stage with ``PYTHONPATH`` cleared, so it exercises
the distributed package (site-packages), not the source tree.

Rather than hardcoding a fixed list of modules/classes (which drifts as the
package grows), this walks every submodule of the installed package and imports
it, then confirms the abstract base classes are importable and are real classes.
Any ImportError anywhere in the package fails the job.

Exit 0 if the wheel is import-clean, 1 otherwise.
"""

from __future__ import annotations

import importlib
import pkgutil
import sys

PACKAGE = "seanergys_modelzoo"

# Abstract base classes every downstream consumer relies on. Import paths are
# stable public API; the concrete models/datasets are validated by walking.
_CORE_CLASSES = [
    ("seanergys_modelzoo.logger.seanergys_logger", "SeanergysLogger"),
    ("seanergys_modelzoo.models.common.seanergys_model", "SeanergysModel"),
    ("seanergys_modelzoo.datasets.common.seanergys_dataset", "SeanergysDataset"),
]


def _import_all_submodules(package_name: str) -> list[tuple[str, str]]:
    """Import every submodule of ``package_name``; return (module, error) failures."""
    failures: list[tuple[str, str]] = []
    try:
        pkg = importlib.import_module(package_name)
    except Exception as e:  # noqa: BLE001 — report any import failure
        return [(package_name, f"{type(e).__name__}: {e}")]

    for mod in pkgutil.walk_packages(pkg.__path__, prefix=f"{package_name}."):
        try:
            importlib.import_module(mod.name)
        except Exception as e:  # noqa: BLE001
            failures.append((mod.name, f"{type(e).__name__}: {e}"))
    return failures


def _check_core_classes() -> list[str]:
    """Confirm each core base class imports and is a class; return error strings."""
    errors: list[str] = []
    for module_path, class_name in _CORE_CLASSES:
        try:
            module = importlib.import_module(module_path)
            obj = getattr(module, class_name)
            if not isinstance(obj, type):
                errors.append(f"{module_path}.{class_name} is not a class")
        except Exception as e:  # noqa: BLE001
            errors.append(f"{module_path}.{class_name}: {type(e).__name__}: {e}")
    return errors


def main() -> int:
    failures = _import_all_submodules(PACKAGE)
    if failures:
        print("✗ Wheel import failures:")
        for name, err in failures:
            print(f"    {name}: {err}")
        return 1

    class_errors = _check_core_classes()
    if class_errors:
        print("✗ Core class checks failed:")
        for err in class_errors:
            print(f"    {err}")
        return 1

    # Count importable submodules for a friendly summary.
    pkg = importlib.import_module(PACKAGE)
    n = sum(1 for _ in pkgutil.walk_packages(pkg.__path__, prefix=f"{PACKAGE}."))
    print(f"✓ {PACKAGE}: {n} submodule(s) import clean; core classes OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
