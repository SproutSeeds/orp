# Mathlib Adapter Notes

Use this adapter when the issue-smashers lane targets
`leanprover-community/mathlib4`.

Source-of-truth behavior currently lives in the stronger reference workflow
developed from `sunflower-coda`:

- issue watch and triage
- viability and etiquette gate
- overlap precheck
- local gate
- ready-to-draft same-head freeze
- PR-body preflight
- draft PR transition
- draft CI and ready-for-review checks
- feedback hardening

Recommended mapping for rendered command variables:

- `WATCH_SELECT_COMMAND` -> watchlist or issue selection script
- `VIABILITY_COMMAND` -> mathlib issue viability gate
- `OVERLAP_COMMAND` -> mathlib overlap precheck
- `LOCAL_GATE_COMMAND` -> mathlib local gate
- `READY_TO_DRAFT_COMMAND` -> mathlib ready-to-draft gate
- `PR_BODY_PREFLIGHT_COMMAND` -> mathlib PR body preflight
- `DRAFT_PR_TRANSITION_COMMAND` -> mathlib draft PR open/update script
- `DRAFT_CI_COMMAND` -> draft CI watcher
- `READY_FOR_REVIEW_COMMAND` -> ready-for-review gate

Use this adapter when you want Issue Smashers ergonomics but mathlib-grade
discipline.
