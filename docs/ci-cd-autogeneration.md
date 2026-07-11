# How the CI/CD docs are auto-generated

This explains the machinery that keeps [`ci-cd.md`](ci-cd.md) — the CI/CD reference we
share with colleagues — in sync with the pipeline automatically, so it never goes stale.
Read this if you need to **change what the tables show**, **add a new generated table**, or
understand the `docs:check` / `docs:autogen` jobs.

`ci-cd.md` is the only auto-generated doc in the repo. This file (and everything else in
`docs/`) is ordinary hand-written Markdown.

## The idea in one line

A generator script reads three sources of truth and rewrites **only** the table regions of
`ci-cd.md`, leaving the hand-written prose untouched — so the "what the CI does" tables can
never drift from the actual pipeline, while the "how to" guide stays human-authored.

## The three sources of truth

`ci/gen_capabilities_doc.py` builds every table from these — nothing is typed into the doc
by hand:

| Source | Supplies | The "what" vs "why" |
|---|---|---|
| `.gitlab-ci.yml` | Jobs, stages, trigger rules, `allow_failure` | the **what** — parsed with PyYAML, anchors resolved |
| The code (via `tests/conftest.py`) | Model×dataset capability matrix, dataset list, test inventory | the **what** — reuses the exact auto-discovery the tests use |
| `ci/policy.yml` | Human rationale that cannot be introspected | the **why** — edited by hand |

Because the *what* comes from the YAML and the code, changing a job or adding a model
updates the tables on the next regeneration with zero manual edits. The *why* is the one
place a human writes prose, and it lives in `ci/policy.yml`.

## How the generator protects hand-written prose

Every generated table sits between a matched pair of HTML-comment markers:

```
<!-- BEGIN:GENERATED jobs -->
| Stage | Job | ... |         ← this region is overwritten on every run
<!-- END:GENERATED jobs -->
```

The generator replaces **only** the text between each `BEGIN`/`END` pair. Anything outside
the markers — the Purpose section, the whole **Developer guide**, this sentence — is never
touched. That is what lets one file hold both auto-generated tables and a human guide.

The generated block names currently are: `pipeline-stages`, `jobs`, `triggers`, `rationale`,
`capabilities`, `datasets`, `test-inventory`, `test-skips`.

## Running it

```bash
make docs-ci          # regenerate docs/ci-cd.md in place
make docs-ci-check    # exit non-zero if the doc is stale (used in CI)
```

Under the hood both call `python ci/gen_capabilities_doc.py` (the second with `--check`).
The generated regions contain **no timestamps**, so regenerating an unchanged repo is a
no-op — this is what makes the auto-commit job loop-safe (see below).

## The two CI jobs that keep it fresh

| Job | Runs on | Does | Blocks? |
|---|---|---|---|
| `docs:check` | merge requests | `gen_capabilities_doc.py --check` — warns if the committed doc is stale | No (warn-only) |
| `docs:autogen` | the default branch | regenerates and **commits** the doc back if it changed | No (warn-only) |

So the workflow is: on an MR, `docs:check` reminds you to run `make docs-ci` if you forgot;
after merge, `docs:autogen` regenerates on `main` and commits any remaining difference, so
the shared doc is always current even if a contributor forgets.

**Loop-safety & auth for `docs:autogen`:** the bot commit uses `[skip ci]` (and
`git push -o ci.skip`) so it does not retrigger the pipeline, and because generated regions
have no timestamps, an unchanged repo produces no commit. The push needs a masked CI/CD
variable `DOCS_BOT_TOKEN` — a Project Access Token with `write_repository`, whose user may
push to the protected default branch. That token is the one manual setup step; everything
else is code.

## How to change what the docs say

Pick the source that owns the fact — never edit `ci-cd.md`'s tables directly:

- **A job, stage, trigger, or `allow_failure` changed** → edit `.gitlab-ci.yml`, then
  `make docs-ci`. The Jobs / Triggers / Pass-fail tables update themselves.
- **A model or dataset was added/removed** → nothing to edit; discovery picks it up. Just
  `make docs-ci` and the capability matrix, dataset list, and test inventory refresh.
- **The rationale (the "why") changed** → edit `ci/policy.yml`. Its sections:
  - `rules:` — one-line description of each trigger anchor.
  - `jobs:` — per-job "why it blocks or warns" (feeds the Pass/fail table).
  - `integration_xfail:` — known-broken `(model, dataset)` pairs, shown as `xfail` in the
    capability matrix (strict xfail; auto-alerts when fixed).
  - `audit_ignore:` — CVEs with no upstream fix yet, fed to `pip-audit` via
    `ci/audit_ignore_flags.py` (keeps `test:audit` green while still reporting everything
    else).
  - `skip_notes:` — implicit skips (e.g. empty-parametrize) that the AST scan can't see,
    surfaced in the Test-skip inventory.
- **A `pytest.skip(...)` or `@pytest.mark.zenodo` was added/removed** → nothing to edit; the
  generator re-scans the test source (AST) and updates the Test-skip inventory.

## How to add a new generated table

1. Add a builder in `_build_blocks()` in `ci/gen_capabilities_doc.py` that puts a rendered
   table (use the `_table(headers, rows)` helper) under a new key, e.g.
   `blocks["my-block"] = _table([...], rows)`.
2. Add the marker pair where you want it to appear in `ci-cd.md`:
   `<!-- BEGIN:GENERATED my-block -->` / `<!-- END:GENERATED my-block -->` (the generator
   warns if a block has no matching marker).
3. Add the same `{my-block}` placeholder to `_DOC_TEMPLATE` so a from-scratch scaffold stays
   consistent.
4. `make docs-ci` to fill it, and `make docs-ci-check` to confirm it's stable.

## Requesting a change without touching code

Colleagues who want a CI rule/gate/capability changed open an issue with the **CI Change
Request** template (`.gitlab/issue_templates/CI_Change_Request.md`). The reviewer edits the
owning source (`.gitlab-ci.yml` or `ci/policy.yml`), regenerates, and the tables follow.

## Files involved

| File | Role |
|---|---|
| `ci/gen_capabilities_doc.py` | The generator (parses YAML, discovers code, scans skips, renders tables) |
| `ci/policy.yml` | Hand-written rationale + ignore/xfail/skip lists |
| `ci/audit_ignore_flags.py` | Emits `--ignore-vuln` flags for `test:audit` from `policy.yml` |
| `docs/ci-cd.md` | The output: auto-generated tables + hand-written Developer guide |
| `.gitlab-ci.yml` | The pipeline itself + the `docs:check` / `docs:autogen` jobs |
| `Makefile` | `docs-ci`, `docs-ci-check` targets |
