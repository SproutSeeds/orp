# Mathlib Adapter Notes

This adapter should be treated as the current reference implementation for the generic
`external-pr-governance` pack.

## Current source of truth

- `docs/EXTERNAL_CONTRIBUTION_GOVERNANCE.md`
- `docs/SUNFLOWER_CODA_PR_GOVERNANCE_MAPPING.md`
- `packs/erdos-open-problems/profiles/sunflower-mathlib-pr-governance.yml.tmpl`
- In the live `sunflower-coda` host repo, the matching docs/scripts for:
  - `MATHLIB_SUBMISSION_CHECKLIST.md`
  - `mathlib-issue-local-gate.sh`
  - `mathlib-ready-to-draft-gate.sh`
  - `mathlib-pr-body-preflight.py`

## Adapter responsibilities

- issue viability decision
- overlap precheck
- local issue gate
- tighten/fine-tooth gate
- ready-to-draft freeze
- PR body preflight
- draft CI watch
- ready-for-review promotion
- maintainer-feedback hardening

## Near-term recommendation

Do not replace the existing `sunflower-mathlib-pr-governance` template yet.

Instead:

1. use it as the strong adapter,
2. keep `external-pr-governance` as the generic contract layer,
3. converge later if the generic pack becomes expressive enough.
