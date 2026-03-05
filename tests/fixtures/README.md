# Test Fixtures

## Future: Real Dataset Sources

When you add real dataset sources (Zenodo, local files, etc.):

1. **Add small sample files** (optional):
   ```
   tests/fixtures/sample_data/
   ├── sample_fdata.parquet   # Small subset for CI
   └── sample_pm100.parquet
   ```

2. **Add max_samples to dataset classes**:
   ```python
   # In FDataDataset, PM100Dataset, etc.
   max_samples: Optional[int] = None  # Limit rows for CI/tests
   ```

3. **Enable commented fixtures in conftest.py**:
   - `synthetic_batch`
   - `synthetic_dataloader`
   - `sample_data_dir`

4. **Enable commented tests in**:
   - `tests/smoke/test_datasets_smoke.py` (dataset instantiation)
   - `tests/smoke/test_models_smoke.py` (model instantiation, train 1 step)

5. **Set CI_MAX_SAMPLES** in `.gitlab-ci.yml` if needed:
   ```yaml
   variables:
     CI_MAX_SAMPLES: "50"
   ```

See `docs/TESTING_AND_CI_PLAN.md` Phase 2–3 for full roadmap.
