<!--
Merge request template for changes to the CI/CD pipeline, its scripts, or the
test suite. Select "CI_Change" from the MR template dropdown.
-->

## Summary

<!-- What does this MR change in the pipeline / tests / CI scripts, and why? -->

## Related

- Closes: #<CI Change Request issue, if any>

## Checklist

- [ ] `.gitlab-ci.yml` change is minimal and scoped
- [ ] `ci/policy.yml` rationale updated for any changed job/rule
- [ ] `docs/ci-cd.md` regenerated (`make docs-ci`) — or the `docs:autogen` job will
- [ ] `make docs-ci-check` passes locally (no doc drift)
- [ ] Tests added/updated for new behaviour
- [ ] `make ci` passes locally (or the relevant subset)
- [ ] No new hardcoded model/dataset names — discovery-driven where possible
- [ ] No secrets, tokens, or credentials added to the repo

## Impact

- [ ] Changes what blocks the pipeline
- [ ] Changes CI runtime/cost
- [ ] Changes the capability matrix
