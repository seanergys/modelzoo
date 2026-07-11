<!--
CI Change Request
Use this template to propose a change to any CI/CD rule, gate, test, or capability.
The current behaviour is documented (auto-generated) in docs/ci-cd.md.
Select this template from the "Choose a template" dropdown when opening an issue.
-->

## What do you want to change?

<!-- Name the exact job / rule / test / capability. Copy the row from docs/ci-cd.md. -->

- **Target job / rule / test:** `<e.g. test:integration, rules_smoke, lint:mypy>`
- **Where it is defined:** `<.gitlab-ci.yml | ci/policy.yml | tests/...>`

## Current behaviour

<!-- What does docs/ci-cd.md say today? Paste the relevant table row(s). -->

| Stage | Job | Trigger | On failure | Runs |
| --- | --- | --- | --- | --- |
|  |  |  |  |  |

## Proposed behaviour

<!-- Precisely what should change: new trigger, block↔warn, added/removed test aspect, new model/dataset pair, etc. -->

## Rationale

<!-- Why. What problem does the current behaviour cause? What does the change buy us? -->

## Impact & risk

- [ ] Changes what **blocks** the pipeline (could stop merges)
- [ ] Changes **CI runtime / cost**
- [ ] Affects the **model×dataset capability matrix**
- [ ] Requires updating `ci/policy.yml` rationale
- [ ] Requires regenerating `docs/ci-cd.md` (`make docs-ci`)
- [ ] Needs new tests

## Sign-off

- **Requested by:**
- **Reviewed by (CI owner):**

/label ~ci ~change-request
