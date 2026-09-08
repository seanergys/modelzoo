# CI/CD Capabilities & Rules Reference

> **This is the single source of truth for testing & CI in this repo.**
> The tables between the `<!-- BEGIN/END:GENERATED -->` markers are **auto-generated**
> by `ci/gen_capabilities_doc.py` from `.gitlab-ci.yml` (jobs/rules), the model/dataset
> code (capability matrix), and `ci/policy.yml` (rationale) — **do not edit them by hand**.
> Regenerate with `make docs-ci`. On the default branch the `docs:autogen` job regenerates
> and commits this file automatically, so the tables never go stale. The prose sections
> (including the [Developer guide](#developer-guide) below) are hand-written and preserved
> across regeneration. For **how the auto-generation works** (sources of truth, the marker
> system, the `docs:check` / `docs:autogen` jobs, how to add a table), see
> [`how-ci-cd-docs-are-generated.md`](how-ci-cd-docs-are-generated.md).
>
> **See also:** [`future_pydantic_tests.md`](future_pydantic_tests.md) (planned Pydantic
> validation tests) and [`MODELZOO_ARCHITECTURE_NOTES.md`](MODELZOO_ARCHITECTURE_NOTES.md)
> (packaging / serving notes). The former developer guide and CI plans were merged into
> this file.

## Purpose

This document is the single reference for **what the CI/CD pipeline tests, and
under which rules**, so it can be shared with colleagues. To request a change to
any rule, gate, or capability, open an issue with the **CI Change Request**
template (`.gitlab/issue_templates/CI_Change_Request.md`).

## Pipeline stages

<!-- BEGIN:GENERATED pipeline-stages -->
**Stage order:** `sanity` → `validate` → `lint` → `test` → `coverage` → `docs` → `build` → `test-wheel`
<!-- END:GENERATED pipeline-stages -->

## Jobs, triggers, and gates

Every job, the condition under which it runs, and whether a failure blocks the
pipeline or only warns.

<!-- BEGIN:GENERATED jobs -->
| Stage | Job | Trigger | On failure | Runs |
| --- | --- | --- | --- | --- |
| sanity | `sanity:check-secrets` | `always` | Blocks | ./ci/check_secrets.sh . |
| sanity | `sanity:check-structure` | `always` | Blocks | test -f pyproject.toml |
| sanity | `sanity:python-syntax` | `always` | Blocks | find seanergys_modelzoo ci tests scripts -name "*.py" -print0 \| xargs -0 -r python -m py… |
| validate | `validate:yaml-json` | `always` | Blocks | python ci/validate_yaml.py |
| lint | `lint:format` | `rules_code` | Warns | ruff format --check seanergys_modelzoo ci tests |
| lint | `lint:mypy` | `rules_code` | Warns | mypy seanergys_modelzoo ci tests --ignore-missing-imports --explicit-package-bases |
| lint | `lint:python` | `rules_code` | Warns | ruff check seanergys_modelzoo ci tests |
| test | `test:audit` | `rules_deps` | Warns | poetry export -f requirements.txt --without-hashes --with dev,ci -o /tmp/poetry-audit-req… |
| test | `test:integration` | `rules_integration` | Blocks | CI_SKIP_ZENODO=1 poetry run pytest tests/integration/ -v -m "not zenodo" --cov=seanergys_… |
| test | `test:smoke-data` | `rules_smoke` | Blocks | poetry run pytest tests/smoke/test_smoke_data.py -v -m "not zenodo" --cov=seanergys_model… |
| test | `test:smoke-models` | `rules_smoke` | Blocks | poetry run pytest tests/smoke/test_smoke_models.py -v --cov=seanergys_modelzoo --cov-repo… |
| test | `test:unit` | `rules_unit` | Blocks | poetry run pytest tests/unit/ -v --tb=short --cov=seanergys_modelzoo --cov-report= |
| test | `test:zenodo` | `rules_zenodo` | Warns | poetry run pytest tests/integration/ -v -m zenodo |
| coverage | `coverage:report` | `rules_code` | Blocks | if ls coverage-data/.coverage.* >/dev/null 2>&1; then coverage combine coverage-data cove… |
| docs | `docs:autogen` | `default-branch` | Warns | poetry run python ci/gen_capabilities_doc.py |
| docs | `docs:check` | `merge-request` | Warns | poetry run python ci/gen_capabilities_doc.py --check |
| build | `build:wheel` | `rules_wheel` | Blocks | poetry build --format wheel |
| test-wheel | `test:wheel` | `rules_wheel` | Blocks | python ci/verify_wheel.py |
<!-- END:GENERATED jobs -->

### Trigger legend

<!-- BEGIN:GENERATED triggers -->
| Trigger | When the job runs |
| --- | --- |
| `always` | Runs on every pipeline (cheap checks < 10s, no change filter). |
| `default-branch` | Runs only on the default branch (post-merge). |
| `merge-request` | Runs on branches / merge requests (excluded on the default branch). |
| `rules_code` | Any source, test, script, CI, or dependency change. |
| `rules_deps` | Only pyproject.toml / poetry.lock / .gitlab-ci.yml changed. |
| `rules_integration` | Source, tests/integration/**, conftest, create_sample_data.py, or deps. |
| `rules_smoke` | Source, tests/smoke/**, conftest, or dependency change. |
| `rules_unit` | Source, tests/unit/**, conftest, or dependency change. |
| `rules_wheel` | Source or pyproject.toml changed (packaging-relevant). |
| `rules_zenodo` | Default branch, or a change under seanergys_modelzoo/datasets/**, tests/integration/**, or conftest. |
<!-- END:GENERATED triggers -->

## Pass / fail engineering decisions

Why each job blocks the pipeline or is allowed to fail. The *what* (above) is
auto-derived from `.gitlab-ci.yml`; the *why* below is maintained in
`ci/policy.yml`.

<!-- BEGIN:GENERATED rationale -->
| Job | On failure | Why |
| --- | --- | --- |
| `sanity:check-secrets` | Blocks | Warn-only: the regex scan can false-positive; a human triages hits. |
| `sanity:check-structure` | Blocks | Guards the repo layout that every later job and import assumes. |
| `sanity:python-syntax` | Blocks | Broken syntax must never enter the pipeline; a cheap hard gate. |
| `validate:yaml-json` | Blocks | Invalid YAML/JSON (incl. this pipeline) would break CI itself — hard gate. |
| `lint:format` | Warns | Formatting drift shouldn't block merges; run `make format` to fix. |
| `lint:mypy` | Warns | Type coverage is incomplete; surfaced as a warning, not a gate. |
| `lint:python` | Warns | Style/lint issues are quality signals, not correctness; non-blocking. |
| `test:audit` | Warns | Dependency CVEs are informational and often unfixable immediately; warn-only. |
| `test:integration` | Blocks | End-to-end model×dataset pipeline must pass; the core correctness gate. |
| `test:smoke-data` | Blocks | Dataset contract + fixtures must load; hard gate (runs without Zenodo). |
| `test:smoke-models` | Blocks | Model discovery/instantiation must hold or nothing downstream works. |
| `test:unit` | Blocks | Component correctness is a hard gate — the fastest signal of breakage. |
| `test:zenodo` | Warns | The only job that reaches Zenodo: downloads a small is_dummy subset (memory-safe capped read — FDataDataset.max_rows via pyarrow.iter_batches over an fsspec HTTP range-request stream, ~136 MB not the ~2 GB whole row group) and runs train→predict→save/load. Warn-only because Zenodo is an external service — downtime must not block merges; a failure is a visible connectivity/regression signal. Flip allow_failure to false to make it a hard gate. |
| `coverage:report` | Blocks | Combines per-job coverage into one report; fails only on tooling error. |
| `docs:autogen` | Warns | Regenerates + commits docs on the default branch; warn-only so a token or push hiccup never breaks main. |
| `docs:check` | Warns | Warns on merge requests when docs/ci-cd.md is stale; not blocking. |
| `build:wheel` | Blocks | A non-buildable package is a release blocker — hard gate. |
| `test:wheel` | Blocks | The distributed wheel must import cleanly for consumers — hard gate. |
<!-- END:GENERATED rationale -->

## Model × dataset capability matrix

Which models are tested against which datasets. Discovered automatically from each
model's `supported_datasets` and the auto-discovery in `tests/conftest.py` — adding
a model or dataset updates this table on the next regeneration.

<!-- BEGIN:GENERATED capabilities -->
| Model | Task | Supported dataset | DATASET_ID | Tested in CI |
| --- | --- | --- | --- | --- |
| JPCP | Regression | PM100Dataset | `pm100` | yes |
| JPCP | Regression | FDataDataset | `f-data` | yes |
| MACK | Classification | FDataDataset | `f-data` | yes |
| MCBound | Classification | FDataDataset | `f-data` | yes |
| RUAD | — | — | `—` | no |
<!-- END:GENERATED capabilities -->

**Legend — the "Tested in CI" column:**

- **`yes`** — the full train → predict → save → load pipeline runs for this pair and **must
  pass** (a hard gate).
- **`xfail`** — short for *expected failure*. The pair is **known-broken**, so its test is
  marked `xfail(strict)`: it still runs, but is *allowed to fail* without turning the
  pipeline red (you'll see it reported as `XFAIL`, not a failure). **"Strict"** adds a safety
  net — if the pair ever unexpectedly *passes*, pytest converts that surprise into a real
  failure (`XPASS`), which forces you to remove the entry from `ci/policy.yml` so the docs
  and reality can't silently drift apart. In other words, `xfail` = "documented as broken on
  purpose, and CI will tell us the moment it's fixed."

**Today no pair is `xfail`, and the list is deliberately kept empty.** `MACK-f-data` and
`MCBound-f-data` **currently fail** — they request `output_features=['mem_compute_bound']`,
a column that exists in no F-DATA file (the real one is `pclass`). That failure is left
**visible** rather than excused: the fix is a modelling decision owned by the model authors,
not something CI may paper over. See the `SUGGESTION` blocks in `mack_model.py`,
`mcbound_model.py` and `f_data.py`, and GitLab issue #10.

> **Ownership.** `ci/`, `tests/`, `.gitlab-ci.yml`, `Makefile`, `scripts/` and `docs/` are
> maintained by the CI/test maintainer. Everything under `seanergys_modelzoo/` — models,
> datasets, common base classes — belongs to the model authors. When a test fails because of
> core code, CI's job is to **report it precisely**, not to fix it and not to hide it.

The `xfail` mechanism stays available, but adding an entry to make a red pipeline green is
explicitly not what it is for — see
[How a known-broken pair is marked `xfail`](#how-a-known-broken-pair-is-marked-xfail-the-mechanism).

## Datasets

<!-- BEGIN:GENERATED datasets -->
| Dataset | DATASET_ID | is_dummy mode |
| --- | --- | --- |
| FDataDataset | `f-data` | yes |
| M100Dataset | `—` | yes |
| PM100Dataset | `pm100` | yes |
| SCRIPTAIDataset | `—` | yes |
<!-- END:GENERATED datasets -->

## Test inventory

Every test file grouped by layer, with the check it performs (from its docstring).

<!-- BEGIN:GENERATED test-inventory -->
| Layer | File | Checks |
| --- | --- | --- |
| unit | `test_configurator.py` | Unit tests for Seanergys configurator (Pydantic params). |
| unit | `test_coverage_extra.py` | Additional unit tests targeting branches not reachable through the happy |
| unit | `test_dataloader.py` | Unit tests for SeanergysDataloader (type guard + from_config). |
| unit | `test_dataloader_params.py` | Unit tests for SeanergysDataloaderParams validation. |
| unit | `test_dataset_contract.py` | Unit tests for dataset contract (__len__, __getitem__, supported_features). |
| unit | `test_dataset_parsers.py` | Unit tests for dataset file/node-spec parsing logic. |
| unit | `test_logger.py` | Unit tests for SeanergysLogger. |
| unit | `test_m100.py` | Unit tests for M100Dataset. |
| unit | `test_metadata.py` | Unit tests for SeanergysModelMetadata. |
| unit | `test_model_subclasses.py` | Unit tests for the concrete model subclasses (MACK, MCBound, JPCP). |
| unit | `test_parquet_datasets.py` | Unit tests for concrete parquet datasets (PM100, F-DATA) using tiny local |
| unit | `test_script_ai.py` | Unit tests for SCRIPTAIDataset using a local features.csv + script files. |
| unit | `test_sklearn_model.py` | Unit tests for SeanergysSklearnModel. |
| unit | `test_utils.py` | Unit tests for ci.utils (discovery helpers). |
| smoke | `test_smoke_data.py` | Smoke tests: dataset discovery, contract validation, and data loading. |
| smoke | `test_smoke_models.py` | Smoke tests: model discovery, instantiation, and train-config structure. |
| integration | `test_model_pipeline.py` | Integration tests: the full pipeline for every (model, dataset) pair. |
<!-- END:GENERATED test-inventory -->

## Test-skip inventory

A skipped test is the one place a **green** pipeline can silently hide an untested
path, so every skip in the suite is inventoried below: where it is, why it skips, and
exactly how to make it run for real. This table is regenerated from the source (the
`pytest.skip(...)` calls and `@pytest.mark.zenodo` markers are scanned via AST; implicit
skips come from `ci/policy.yml` `skip_notes`), so it can never drift from the code.

<!-- BEGIN:GENERATED test-skips -->
| File | Test (line) | Reason | How to remove the skip |
| --- | --- | --- | --- |
| `tests/integration/test_model_pipeline.py` | `test_full_pipeline_zenodo` (L191) | Needs a live Zenodo download; deselected by `-m "not zenodo"` and skipped when CI_SKIP_ZENODO=1. | Runs for real in the `test:zenodo` job. |
| `tests/integration/test_model_pipeline.py` | `test_full_pipeline_zenodo` (L196) | CI_SKIP_ZENODO=1 — Zenodo tests disabled for this run. | Runs for real in the `test:zenodo` job (no CI_SKIP_ZENODO); locally run with network. |
| `tests/integration/test_model_pipeline.py` | `test_full_pipeline_zenodo` (L209) | {…}/{…}: is_dummy=True returned 0 rows | Implement dummy support in {…}. |
| `tests/smoke/test_smoke_data.py` | `test_dataset_contract_via_model_config` + 2 more (empty parametrize) | Under CI_SKIP_ZENODO=1, _collect_dataset_configs_from_models() returns {} because building the config instantiates datasets that connect to Zenodo at collection time — so these tests parametrize to zero cases and report 'empty parameter set'. | Exercised for real by the `test:zenodo` job. Full offline fix: make each model's get_train_config() assemble params WITHOUT instantiating its dataset. |
| `tests/smoke/test_smoke_data.py` | `test_dataset_fixture_has_data` (L185) | fixture not found: {…} | Run `make sample-data` to create it. |
| `tests/smoke/test_smoke_data.py` | `test_dataset_loads_from_zenodo` (L255) | Needs a live Zenodo download; deselected by `-m "not zenodo"` and skipped when CI_SKIP_ZENODO=1. | Runs for real in the `test:zenodo` job. |
| `tests/smoke/test_smoke_data.py` | `test_dataset_loads_from_zenodo` (L272) | CI_SKIP_ZENODO=1 — Zenodo tests disabled for this run. | Runs for real in the `test:zenodo` job (no CI_SKIP_ZENODO); locally run with network. |
| `tests/smoke/test_smoke_data.py` | `test_dataset_loads_from_zenodo` (L283) | use_zenodo_url=True not supported. | Add use_zenodo_url field to {…} to enable Zenodo testing. |
| `tests/smoke/test_smoke_data.py` | `test_dataset_loads_with_is_dummy` (L203) | Needs a live Zenodo download; deselected by `-m "not zenodo"` and skipped when CI_SKIP_ZENODO=1. | Runs for real in the `test:zenodo` job. |
| `tests/smoke/test_smoke_data.py` | `test_dataset_loads_with_is_dummy` (L222) | CI_SKIP_ZENODO=1 — Zenodo tests disabled for this run. | Runs for real in the `test:zenodo` job (no CI_SKIP_ZENODO); locally run with network. |
| `tests/smoke/test_smoke_models.py` | `test_model_get_train_config` (L116) | get_train_config() returned None. | Implement get_train_config() in {…} to enable this test. |
<!-- END:GENERATED test-skips -->

---

# Developer guide

Everything below is hand-written prose (preserved across regeneration). It is the
merged, updated content of the former `TESTING_AND_CI_GUIDE.md` and the old CI plans.

## Setting up a machine

The only things you must have are `curl`, `git` and `make`. Everything else is installed
for you on first use, into `~/.local/bin` and `.venv/.

```bash
make test           # on a fresh clone this bootstraps the machine, then runs the tests
```

Every target that needs a working environment depends on `make env`, which chains three
guarded steps and skips any of them that is already satisfied:

| Step | Target | What it guarantees |
|---|---|---|
| 1 | `make tools` | `curl`/`git`/`make` present; **uv** and **poetry** installed if missing; a Python in `>=3.12,<3.15` (fetched with `uv python install` if the system one is out of range). Runs `scripts/ensure_tools.sh`. |
| 2 | `make deps-check` | `poetry.lock` is in sync with `pyproject.toml` (`poetry check --lock`) |
| 3 | `$(VENV)/.deps-installed` | `.venv/` exists and `poetry install --with dev,ci` has run. The stamp file depends on `pyproject.toml` and `poetry.lock`, so the install re-runs **only** when one of them actually changed. |

Useful setup targets:

| Command | Does |
|---|---|
| `make bootstrap` | The whole setup explicitly, without running tests |
| `make doctor` | Reports toolchain / `.venv` / fixture state and changes nothing |
| `make tools` | Toolchain only — installs what is missing |
| `make tools-check` | Toolchain only — **never** installs, non-zero exit if incomplete |
| `make env` | Toolchain + lock check + `.venv` synced to `poetry.lock` |
| `make install` | `dev` group only (tooling). Not enough to run the tests — they import torch/sklearn through the package — so it clears the stamp and the next test target reinstalls `dev,ci`. |
| `make install-ci` | `dev` + `ci` groups (same as `make env`) |
| `make clean-venv` | Deletes `.venv/`; the next make target rebuilds it |

**Environment switches:**

| Variable | Effect |
|---|---|
| `MODELZOO_NO_AUTO_INSTALL=1` | Never install machine tools — report what is missing and fail. Use on locked-down machines and in images that must not fetch anything. |
| `PYTHON_BIN=/usr/bin/python3.13` | Force the interpreter used to create `.venv/` |
| `PYTHON_KEYRING_BACKEND=…` | Defaults to the **null** backend. Poetry otherwise queries the system keyring and aborts mid-install on sessions without an unlocked DBus secret service (`DBusErrorResponse` → `Cannot install <pkg>`). Override only if you add a private package index. |
| `CI_SKIP_ZENODO=1` | Never touch the network; offline fixtures only |

If a fresh shell cannot find `uv`/`poetry` afterwards, add `export PATH="$HOME/.local/bin:$PATH"`
to your `~/.bashrc`.

## Running the tests locally

Run the tests before every push — it is faster than waiting for a red pipeline. No setup
command is required first; each of these bootstraps what it needs.

```bash
make sample-data    # optional — refreshes the Zenodo fixtures (they are committed already)
```

| Command | Runs | When |
|---|---|---|
| `make test` | unit + smoke (offline, fast) | **before every push** |
| `make test-unit` | `tests/unit/` | changing base classes / utils |
| `make test-smoke-models` | `tests/smoke/test_smoke_models.py` | model discovery / instantiation |
| `make test-smoke-data` | `tests/smoke/test_smoke_data.py` | dataset contract / fixtures |
| `make test-pipeline` | full train→predict→save→load per model | changing model code |
| `make test-integration` | `tests/integration/` (offline, fixtures) | before opening an MR |
| `make test-all` | unit + smoke + integration | final check before an MR |
| `make test-wheel` | build the wheel and verify it imports | packaging changes |
| `make lint` / `make format` / `make typecheck` | ruff check / ruff format / mypy | quality gates |
| `make docs-ci` / `make docs-ci-check` | regenerate / drift-check this file | after CI or test changes |
| `make pre-push` | format-check + check-secrets + lint + test | the full local gate |
| `make ci` | mirrors the whole GitLab pipeline offline | simulate CI locally |

**Skip Zenodo network locally** (uses committed fixtures only, no downloads):

```bash
CI_SKIP_ZENODO=1 make test-integration
```

**Run a single test file or test:**

```bash
.venv/bin/pytest tests/unit/test_configurator.py -v
.venv/bin/pytest tests/smoke/test_smoke_models.py::test_model_discovery -v
```

## What each test layer checks

- **unit** (`tests/unit/`) — component correctness in isolation: Pydantic params,
  base-class contracts, dataset parsers, per-class dataset internals (parsing, node
  ranges), the sklearn wrapper. Hard gate.
- **smoke** (`tests/smoke/`) — cheap end-to-end sanity without training: every model and
  dataset is **discovered** (`tests/conftest.py`), instantiates, and its `get_train_config`
  has the right shape; fixtures load. Hard gate, runs offline.
- **integration** (`tests/integration/test_model_pipeline.py`) — the full
  train→predict→save→load lifecycle for **every discovered (model, dataset) pair**, offline
  against committed fixtures. Any failure names the exact pair **and** stage. Hard gate.
- **zenodo** (`test:zenodo`, `-m zenodo`) — the same lifecycle against a real `is_dummy=True`
  download from Zenodo. The **only** job that touches the network; warn-only.

## `is_dummy=True` and memory-safe Zenodo loading

`is_dummy=True` gives each dataset a tiny **real** slice of its data for testing. For
F-DATA it sets `files="21_04"` and a small **row cap** (`max_rows=200`): the read goes
through `FDataDataset._read_parquet`, which uses `pyarrow.ParquetFile.iter_batches` over an
`fsspec` HTTP **range-request** stream and stops after the first 200 rows. This matters
because F-DATA's monthly files are a **single row group**, so a `filters=` predicate cannot
push down — a plain `pd.read_parquet(url, columns=, filters=)` would still materialise the
whole group (~2 GB). The capped read fetches only the selected columns' chunks (~136 MB) and
never OOMs the runner. `max_rows=None` (the default) restores the plain read for local files.
This needs `aiohttp` + `fsspec` (declared in the `ci` dependency group).

## Adding a new model or dataset

The suite is **auto-discovery driven**, so a new model or dataset enters CI by contract —
no test or table to edit by hand.

1. Create `seanergys_modelzoo/models/tasks/<task>/<model_name>/<model_name>_model.py`.
2. Subclass `SeanergysSklearnModel` (or `SeanergysModel` for non-sklearn).
3. Implement `get_train_config(dataset_id)` returning
   `Dict[str, Tuple[model_instance, DatasetClass, (SeanergysDatasetParams, SeanergysDataloaderParams)]]`,
   and raise on an unknown `dataset_id` (see `JPCP` for the pattern).
4. Ensure each dataset it uses supports `is_dummy=True` (CI exercises this without real data).
5. `tests/conftest.py` discovers the model, adds its `(model, dataset)` pairs to
   `MODEL_DATASET_PAIRS`, and the smoke/integration/capability tables pick it up on the next
   run. Regenerate this doc with `make docs-ci`.

If a (model, dataset) pair is known-broken, add it to `integration_xfail` in `ci/policy.yml`
(strict xfail — it auto-alerts when the fix lands) rather than skipping it in test code.

## Common workflows

- **Fresh clone / new machine:** nothing — `make test` sets everything up. `make doctor` if you want to see the state first.
- **Before every push:** `make pre-push` (format-check + secrets + lint + unit/smoke).
- **Before opening an MR:** `make test-all` and `make docs-ci-check`.
- **After changing `.gitlab-ci.yml`, `ci/policy.yml`, or test structure:** `make docs-ci`
  to regenerate the tables above, and commit the result.
- **To request a CI change (colleagues):** open an issue with the **CI Change Request**
  template (`.gitlab/issue_templates/CI_Change_Request.md`).

## Tooling

`pytest` (+ `pytest-cov`) for tests; `ruff` for lint **and** formatting (Black is not used
in CI); `mypy` for types; `pip-audit` for dependency CVEs (see `ci/policy.yml` `audit_ignore`);
`py_compile` for the syntax gate; `PyYAML` for the doc generator and validators. Dependencies
are managed with Poetry groups: `dev` (tooling) and `ci` (the full ML stack); CI installs
`--with dev,ci`, and locally `make env` does the same.

The machine toolchain itself — `uv`, a supported Python, and `poetry` — is bootstrapped by
`scripts/ensure_tools.sh`, which every `make` target reaches through `make tools`. `uv` is
used as the installer for `poetry` (`uv tool install poetry`) and as the fallback Python
version manager (`uv python install 3.13`); it is not used to resolve project dependencies —
`poetry.lock` remains the single source of truth.

## Design decisions & known limitations

- **Datasets are testable only through a model's `get_train_config()`.** A dataset needs
  `input_features` / `output_features` to be constructed, and those come from the model
  config — there is no self-describing `get_dummy_params()` on datasets. So a dataset with
  no model referencing it gets **discovered but not exercised**.
- **`SCRIPTAIDataset` is currently orphaned:** no model lists it in `supported_datasets`, so
  it appears in discovery (DATASET_ID `—`) but no pipeline/contract test runs on it. To cover
  it, add it to a model's `get_train_config()` (then it inherits fixtures, contract, and
  Zenodo tests for free). `M100Dataset` is likewise not wired to a model.
- **`importorskip` is banned in tests.** Every job runs the full `.install_ci` venv, so an
  `importorskip` could only fire on a broken environment — silently skipping and turning
  "nothing tested" into a green run. Import test dependencies directly so a missing dep fails
  loudly at collection.
- **No pair is excused from the pipeline, and two of them fail.** `integration_xfail` in
  `ci/policy.yml` is empty, so nothing is masked: `pytest --runxfail` produces exactly the
  same result as a normal run. `MACK-f-data` and `MCBound-f-data` fail because they target
  `output_features=['mem_compute_bound']`, a column absent from every F-DATA file — the
  published memory/compute-bound label is `pclass`. Two further problems surface once that is
  corrected: MACK reads `df.memory_bw` (the real column is `mbwidth`) and overwrites
  `df["pclass"]` with a tuple, which torch's `default_collate` rejects. All three are written
  up as `SUGGESTION` blocks inside the owning source files and tracked in issue #10. **CI
  reports this; CI does not fix it and does not hide it.**

## How a known-broken pair is marked `xfail` (the mechanism)

> **The list is empty today and stays empty.** This section documents the mechanism, not a
> licence to use it. Two pairs are red right now (`MACK-f-data`, `MCBound-f-data`) and they
> are deliberately **not** listed here: a defect in a shipped model must be visible in the
> pipeline. Adding an entry to silence a red test is the one use this mechanism must never
> be put to.

CI "knows" a pair is expected-to-fail because the **test reads the list from `ci/policy.yml`
at collection time** and tags exactly those parametrized cases — nothing is hard-coded in
the test. The chain is:

**1. The list lives in `ci/policy.yml`** (shown here with a hypothetical entry; the real
file has `integration_xfail: {}`):

```yaml
integration_xfail:
  SomeModel-some-dataset: "why it is broken, and what the fix depends on"
```

**2. `tests/integration/conftest.py` reads it** (`load_known_xfails()`) into a dict
`{"SomeModel-some-dataset": "reason"}` — an empty dict when the section is empty.

**3. `tests/integration/test_model_pipeline.py` attaches a strict-xfail marker to matching
pairs when it builds its parametrization:**

```python
_XFAILS = load_known_xfails()                           # from policy.yml

def _pipeline_params():
    params = []
    for model_cls, dataset_id in MODEL_DATASET_PAIRS:    # auto-discovered pairs
        key = f"{model_cls.__name__}-{dataset_id}"       # e.g. "MACK-f-data"
        marks = []
        if key in _XFAILS:                               # ← known-broken?
            marks.append(pytest.mark.xfail(reason=_XFAILS[key], strict=True))
        params.append(pytest.param(model_cls, dataset_id, id=key, marks=marks))
    return params
```

So a listed pair carries `xfail(strict=True)`; every other pair — which today means *all*
of them — carries no marker and is an ordinary must-pass test.

**4. At run time pytest decides the outcome:**

- The test runs, tries to train, and **raises**. Because the case has an `xfail` marker,
  pytest records that as **`XFAIL`** — an *accepted* result, **not** a failure. The job exit
  code stays `0` → the pipeline is green (`… 1 xfailed`). This is exactly why the list must
  stay empty: an `XFAIL` is a test that is not really testing anything.
- `strict=True` is the guard: if the test had instead **passed**, pytest records **`XPASS`**
  and — being strict — converts it into a **real failure** (job red), forcing you to delete
  the `policy.yml` entry. That is the self-correcting "tell me the moment it's fixed" loop.

**Why the same pair can PASS one test and XFAIL another:** there are two parametrization
lists on purpose.

| List | Marker | Used by | Result for a listed pair |
|---|---|---|---|
| `_PLAIN_PARAMS` | none | `test_get_train_config_structure` (config shape only, no data) | **PASSED** — building the config never loads data |
| `_PIPELINE_PARAMS` | `xfail(strict)` on known-broken pairs | `test_full_pipeline_offline` / `…_zenodo` (loads data + trains) | **XFAIL** — the real breakage is hit |

With the list empty, both lists behave identically and every pair must pass in both.
