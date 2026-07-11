# ADR 0001 — Self-documenting CI capabilities, path-based skipping, auto-committed docs

- **Status:** Accepted
- **Deciders:** Mohsen Seyedkazemi Ardebili
- **Context date:** 2026-07-11

## Context

The GitLab CI/CD pipeline (`.gitlab-ci.yml`) had accumulated defects and was
undocumented at the level colleagues could review:

- `test:integration` re-ran `tests/unit/` + `tests/smoke/*` on top of the dedicated
  jobs, so unit and smoke tests executed **twice** per pipeline and a failure inside
  integration was ambiguous about which layer broke.
- `test:unit` ran under a dev-only environment (no `torch`/`sklearn`), but the unit
  tests import those through the package — the job was misconfigured.
- The integration pair-test `pytest.skip`ped on setup errors (silent), and in CI
  (`CI_SKIP_ZENODO=1`) the fixture-based tests silently skipped every model whose only
  fixture (`sample_fdata.parquet`) was not committed.
- `test:wheel` hard-coded four import checks that drift as the package grows.
- There was **no single document** describing what the pipeline tests, its rules, and
  its pass/fail decisions — and no mechanism to keep such a document from going stale.

We needed: correctness + de-duplication; a way to avoid re-running work; a complete,
precise integration test; and a shareable capabilities/rules report that cannot drift.

## Decision

1. **Run each test layer exactly once; combine coverage.** Unit, smoke-models,
   smoke-data, and integration each emit a partial coverage data file; a `coverage`
   stage combines them into one cobertura report. All test jobs share one cached
   in-project `.venv` with the full ML stack.

2. **Path-based `rules:changes` + cached venv — not a fingerprint manifest.** To avoid
   redoing work we (a) scope each job's `rules` to the files it depends on
   (`rules_unit`/`rules_smoke`/`rules_integration`) and (b) cache `.venv` keyed on
   `poetry.lock` so `poetry install` is a near no-op on a cache hit. We rejected a
   per-pair fingerprint/skip manifest: with `is_dummy`/fixture data the pair tests are
   already fast, so the real cost was dependency installation, and a fingerprint cache
   adds cache-invalidation complexity and flakiness for little gain. Skipping is
   therefore **job-level**, not per-model — a change under `seanergys_modelzoo/**`
   reruns every test job because the core code is shared.

3. **Auto-generated, auto-committed capability/rules doc.** `docs/ci-cd.md` is generated
   by `ci/gen_capabilities_doc.py` from three sources: `.gitlab-ci.yml` (jobs, triggers,
   `allow_failure`), the model/dataset discovery in `tests/conftest.py` (capability
   matrix + test inventory), and `ci/policy.yml` (hand-maintained rationale). Only the
   regions between `GENERATED` markers are rewritten. Generated regions contain **no
   timestamps** so regeneration is a no-op when nothing changed. On the default branch a
   `docs:autogen` job regenerates and commits the doc back (`[skip ci]` + `-o ci.skip`
   to avoid a pipeline loop) using a Project Access Token; on branches/MRs a
   non-blocking `docs:check` warns on drift.

4. **Dynamic wheel verification.** `ci/verify_wheel.py` walks every submodule of the
   installed package and imports it, replacing the four hard-coded import checks.

## Consequences

**Positive**

- No duplicated test execution; a failure names its own job/layer.
- The capability/rules report (`docs/ci-cd.md`) cannot drift from the YAML/code — the
  *what* is auto-derived; only the *why* (`ci/policy.yml`) is edited by hand, in one
  place. Colleagues review a current document and request changes via the
  `CI Change Request` issue template.
- Faster pipelines on a warm cache; fewer jobs run on unrelated changes.

**Negative / costs**

- `docs:autogen` requires a **Project Access Token** (`write_repository`) stored as the
  masked CI variable `DOCS_BOT_TOKEN`, and the token's user must be allowed to push to
  the protected default branch. This is a one-time manual setup; the job is
  `allow_failure: true` so a missing token never breaks `main`.
- Job-level skipping can under-count combined coverage on a partial-change pipeline
  (skipped layers contribute no data); full coverage is produced whenever core code
  changes. This is documented in `docs/ci-cd.md`.
- Committing per-dataset fixtures (so integration runs offline and never silently skips)
  adds small binary parquet files to the repo.

## Alternatives considered

- **Fingerprint/manifest per-pair test skipping** — rejected (complexity/flakiness vs.
  low benefit; see decision 2).
- **Blocking stale-doc gate** — rejected in favour of auto-commit, so authors never have
  to hand-regenerate; the doc is always current on `main`.
- **Manually maintained capabilities table** — rejected; that is exactly the drift
  problem this ADR removes.
