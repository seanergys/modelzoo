# Test Fixtures

## Sample Data (for local and CI tests)

Small parquet files for dataset load tests. Created by `make sample-data` from Zenodo.

### Create sample data

```bash
# From project root
make sample-data

# Limit rows (default: 100)
SAMPLE_MAX_ROWS=50 make sample-data

# Create only one dataset
make sample-data ARGS='--fdata-only'
make sample-data ARGS='--pm100-only'
```

### Output

```
tests/fixtures/sample_data/
├── sample_fdata.parquet   # F-DATA subset (~100 rows)
└── sample_pm100.parquet  # PM100 subset (~100 rows)
```

### Usage in tests

- `tests/smoke/test_datasets_load.py` uses these fixtures when present.
- If fixtures are missing, local-fixture tests are skipped; Zenodo tests may run (unless `CI_SKIP_ZENODO=1`).
- CI: run `make sample-data` in a before_script or cache the fixtures.

### Manual script

```bash
python scripts/create_sample_data.py
python scripts/create_sample_data.py --max-rows 50 --fdata-only
```

## See also

- `docs/TESTING_AND_CI_PLAN.md` — full test strategy
- `Makefile` — `make help` for all targets
