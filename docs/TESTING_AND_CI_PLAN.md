# Complete Testing & CI/CD/MLOps Plan

## Overview

This document defines the full testing strategy for seanergys-modelzoo across:

### Pytest

**Pytest** is the testing framework for unit, smoke, and integration tests:

- **Discovery**: Finds `test_*.py` files and `test_*` functions automatically
- **Run**: `pytest tests/` or `pytest tests/unit/ -v`
- **Assertions**: Use `assert`; pytest gives clear failure output
- **Fixtures**: Shared setup in `conftest.py` (e.g. temp dirs, synthetic data)
- **Install**: `pip install pytest` (see `requirements-test.txt`)

Pytest complements the CI validation scripts (`ci/validate_models.py`, etc.): scripts handle discovery and full runs; pytest handles granular, fast, isolated checks.

- **DevOps** — infrastructure, config, code quality
- **ML/MLOps** — models, datasets, training, inference
- **Subset data** — all tests use small subsets, never full datasets
- **Scalability** — many models (different I/O) and datasets during development

---

## 1. Test Taxonomy

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        E2E (Full pipeline, manual/scheduled)                │
│  Training job → Model registry → Inference API (when ML pipeline exists)    │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
┌───────────────────────────────────────┴─────────────────────────────────────┐
│                    Integration (Model + Dataset + Save/Load)                │
│  Train on subset → Predict → Save → Load. Run on CI + ML pipeline.          │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
┌───────────────────────────────────────┴─────────────────────────────────────┐
│                         Smoke (Instantiation & Quick sanity)                │
│  Discover models/datasets → Instantiate with subset → No full train.        │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
┌───────────────────────────────────────┴─────────────────────────────────────┐
│                         Unit (Isolated components)                          │
│  Utils, configs, single class/fn. Mocks, no I/O.                            │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
┌───────────────────────────────────────┴─────────────────────────────────────┐
│                    DevOps (Code quality, config, build)                     │
│  Lint, type check, YAML/JSON, syntax, security scan, dependencies.          │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Complete Test List

### 2.1 DevOps Tests (CI pipeline — every push/MR)

| # | Test | What it checks | When | Tool/Command |
|---|------|----------------|------|--------------|
| D1 | **Syntax** | Python compiles | Always | `python -m py_compile` |
| D2 | **Structure** | Repo layout (setup.py, package dirs) | Always | shell checks |
| D3 | **Lint** | Style, unused vars, complexity | On .py changes | ruff / flake8 |
| D4 | **Format** | Code formatting | On .py changes | black / ruff format |
| D5 | **Type check** | Type hints correct | On .py changes | mypy |
| D6 | **Config validation** | YAML/JSON parseable | On config changes | ci/validate_yaml.py |
| D7 | **Dependencies** | No known vulnerabilities | On dep changes | pip-audit / safety |
| D8 | **Import sanity** | Package imports | Always | `python -c "import seanergys_modelzoo"` |
| D9 | **Secret scan** | No secrets in code | Always | grep / gitleaks |
| D10 | **Documentation** | Docstrings / API docs build | Optional | pydoc / mkdocs |

### 2.2 Unit Tests (pytest — every push)

| # | Test | What it checks | Data |
|---|------|----------------|------|
| U1 | **Discovery utils** | `retrieve_instances_from_file`, `import_module_from_file` | Mock modules |
| U2 | **Logger** | SeanergysLogger init, log levels | None |
| U3 | **Configurator** | Pydantic configs (SeanergysModelParams, etc.) | Dict fixtures |
| U4 | **Dataset contract** | `__len__`, `__getitem__`, `supported_features` | Synthetic tensors |
| U5 | **Model metadata** | SeanergysModelMetadata serialize/deserialize | None |
| U6 | **Dataloader params** | SeanergysDataloaderParams validation | Dict fixtures |

### 2.3 Smoke Tests (pytest — every push)

| # | Test | What it checks | Data |
|---|------|----------------|------|
| S1 | **Model discovery** | All SeanergysModel subclasses found | None |
| S2 | **Model instantiation** | Each model instantiates with minimal config | No real data |
| S3 | **Dataset discovery** | All SeanergysDataset subclasses found | None |
| S4 | **Dataset instantiation** | Each dataset instantiates (subset if needed) | `max_samples=10` |
| S5 | **Model–dataset compatibility** | Model.supported_datasets includes dataset | None |

### 2.4 Integration Tests (subset data — MR or scheduled)

| # | Test | What it checks | Data |
|---|------|----------------|------|
| I1 | **Model + Dataset train** | train() runs 1–2 steps on subset | `max_samples=50` |
| I2 | **Model predict** | predict() returns valid output | Same subset |
| I3 | **Model save/load** | save() + load() round-trip | Temp dir |
| I4 | **Full flow** | train → predict → save → load | Subset |
| I5 | **Model–dataset pairs** | Each (model, dataset) pair that supports each other | Subset per pair |

### 2.5 E2E Tests (ML pipeline — when available)

| # | Test | What it checks | Where |
|---|------|----------------|-------|
| E1 | **Training job** | Full training run produces artifact | ML pipeline |
| E2 | **Model registry** | Model stored and retrievable | ML pipeline |
| E3 | **Inference** | Predict from served model | ML pipeline |
| E4 | **Data pipeline** | Data ingest → preprocess → dataset | ML pipeline |
| E5 | **Reproducibility** | Same config → same result (deterministic) | ML pipeline |

---

## 3. Data Strategy (Subset-First)

All ML tests use **subset of dataset**:

| Mechanism | Implementation |
|-----------|----------------|
| **max_samples** | Add `max_samples: Optional[int]` to dataset init; limit `__len__` |
| **limit in filters** | Use filters to restrict rows (e.g. date range, first N) |
| **Fixture files** | `tests/fixtures/sample_*.parquet` (small, committed or cached) |
| **Synthetic** | `torch.randn(n, d)` or `pd.DataFrame` for unit/smoke |
| **Env var** | `CI_MAX_SAMPLES=50` for CI overrides |

**Per-model flexibility:** Each model has different I/O. Use:
- Discovery + interface contract (train/predict/save/load)
- Per-model `run_dummy_validation` with subset params
- Fixture registry: `{"JPCP": fixture_jpcp, "MACK": fixture_mack, ...}`

---

## 4. CI Pipeline (Now)

### Stages (order)

```
sanity → validate → lint → unit → smoke → integration
```

### Job Matrix

| Stage | Jobs | Triggers | Allow failure |
|-------|------|----------|---------------|
| sanity | syntax, structure | Always | No |
| validate | yaml-json, configs | On config change / always | Config: No |
| lint | ruff, black, mypy | On .py change | Yes (initially) |
| unit | pytest tests/unit/ | On .py change | No |
| smoke | pytest tests/smoke/ | On .py change | No |
| integration | pytest tests/integration/ | On model/dataset change or MR | No (or manual) |

### Example rules

```yaml
# Unit: every push
test:unit:
  script: pytest tests/unit/ -v
  rules: - changes: ["**/*.py"]

# Smoke: every push
test:smoke:
  script: pytest tests/smoke/ -v
  rules: - changes: ["**/*.py"]

# Integration: MR or when models/datasets change
test:integration:
  script: pytest tests/integration/ -v --tb=short
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
    - changes: ["seanergys_modelzoo/models/**", "seanergys_modelzoo/datasets/**"]
```

---

## 5. ML Pipeline (Future — MLOps)

When you add an ML pipeline (Airflow, Kubeflow, custom, etc.):

| Component | Purpose |
|-----------|---------|
| **Data pipeline** | Ingest, preprocess, validate, store subset/features |
| **Training pipeline** | Train models on subset/full, log metrics, save artifacts |
| **Model registry** | Store model versions, metadata |
| **Serving** | Inference API or batch prediction |
| **Monitoring** | Drift, performance, data quality |

### Shared tests (CI + ML pipeline)

These run in **CI** (quick subset) and **ML pipeline** (full or larger subset):

| Test | CI | ML pipeline |
|------|----|-------------|
| Model train 1 step | ✓ subset | ✓ full |
| Model save/load | ✓ | ✓ |
| Predict output shape | ✓ | ✓ |
| Reproducibility (seed) | ✓ | ✓ |

**Implementation:** Same pytest tests, different config:
- CI: `pytest tests/integration/ -v` (uses `CI_MAX_SAMPLES=50`)
- ML: `pytest tests/integration/ -v --ml-pipeline` (uses full or `MAX_SAMPLES=1000`)

---

## 6. Directory Layout

```
seanergys_modelzoo/
├── models/
├── datasets/
├── dataloader/
├── logger/
└── ...

tests/
├── unit/
│   ├── test_utils.py
│   ├── test_logger.py
│   ├── test_configurator.py
│   └── test_dataset_contract.py
├── smoke/
│   ├── test_models_smoke.py
│   └── test_datasets_smoke.py
├── integration/
│   ├── test_model_train.py
│   ├── test_model_save_load.py
│   └── test_model_dataset_pairs.py
├── e2e/                    # When ML pipeline exists
│   ├── test_training_job.py
│   └── test_inference.py
├── fixtures/
│   ├── sample_data/        # Small parquet/csv
│   └── configs/            # Test configs
├── conftest.py             # Pytest fixtures, max_samples
└── helpers/
    └── seanergys_model_evaluator.py

ci/
├── validate_yaml.py
├── validate_models.py
├── validate_datasets.py
├── utils.py
├── requirements-ci.txt
└── seanergys_model_evaluator.py

requirements-test.txt   # pytest, pydantic (for unit/smoke)
```

---

## 7. Implementation Roadmap

### Phase 1: Foundation (Week 1) ✓

| Task | Description | Status |
|------|-------------|--------|
| 1.1 | Fix `ci/utils.py` (importlib.util) | ✓ |
| 1.2 | Fix `validate_models.py` (argparse, run_dummy) | ✓ |
| 1.3 | Fix `validate_datasets.py` (discovery, main signature) | ✓ |
| 1.4 | Add `pytest`, `conftest.py`, `max_samples` env handling | ✓ |
| 1.5 | Create `tests/unit/test_utils.py` | ✓ |
| 1.6 | Update CI: add `test:unit` job | ✓ |

### Phase 2: Smoke + Dataset Subset (Week 2)

| Task | Description |
|------|-------------|
| 2.1 | Add `max_samples` to dataset classes (or wrapper) |
| 2.2 | Create `tests/smoke/test_models_smoke.py` |
| 2.3 | Create `tests/smoke/test_datasets_smoke.py` |
| 2.4 | Add `test:smoke` to CI |

### Phase 3: Integration (Week 3)

| Task | Description |
|------|-------------|
| 3.1 | Create `tests/fixtures/` with small samples or synthetic |
| 3.2 | Create `tests/integration/test_model_train.py` |
| 3.3 | Create `tests/integration/test_model_save_load.py` |
| 3.4 | Add `test:integration` to CI (MR or changes) |

### Phase 4: DevOps Hardening (Week 4)

| Task | Description |
|------|-------------|
| 4.1 | Add ruff/black config (`pyproject.toml`) |
| 4.2 | Add mypy (optional, allow_failure) |
| 4.3 | Add pip-audit or safety |
| 4.4 | Document all jobs in `docs/CI.md` |

### Phase 5: ML Pipeline (Future)

| Task | Description |
|------|-------------|
| 5.1 | Define ML pipeline (Airflow/DVC/Kubeflow/…) |
| 5.2 | Add `tests/e2e/` for pipeline-specific tests |
| 5.3 | Wire shared integration tests to ML pipeline |
| 5.4 | Add model registry + monitoring |

---

## 8. Checklist Summary

### DevOps

- [ ] D1 Syntax
- [ ] D2 Structure
- [ ] D3 Lint (ruff)
- [ ] D4 Format (black/ruff)
- [ ] D5 Type check (mypy)
- [ ] D6 Config validation
- [ ] D7 Dependencies audit
- [ ] D8 Import sanity
- [ ] D9 Secret scan
- [ ] D10 Documentation (optional)

### ML Tests

- [x] U1 Discovery utils (test_utils.py)
- [ ] U2–U6 Unit (logger, configurator, etc.)
- [x] S1–S2 Smoke (logger, ci.utils imports)
- [ ] S3–S5 Smoke (dataset discovery, model instantiation)
- [ ] I1–I5 Integration (subset)
- [ ] E1–E5 E2E (when ML pipeline exists)

### Data

- [ ] max_samples / subset support in datasets
- [ ] tests/fixtures/ with small samples
- [ ] CI_MAX_SAMPLES env for CI

### CI

- [x] sanity, validate, lint stages
- [x] unit, smoke stages (pytest)
- [ ] integration stage
- [ ] Rules: changes, MR
- [ ] Caching (pip)

### Future (ML pipeline)

- [ ] E2E job in ML pipeline
- [ ] Shared integration tests
- [ ] Model registry
- [ ] Monitoring
