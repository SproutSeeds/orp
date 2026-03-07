# Sunflower Adapter Dependencies (857/20/367)

This pack keeps ORP core generic while exposing optional sunflower-coda adapters.

When you install `erdos-open-problems` with:

`./scripts/orp pack install --pack-id erdos-open-problems ...`

ORP writes an install report with dependency audit counts.
By default, ORP also scaffolds starter adapter files for 857/20/367 (`--no-bootstrap` disables this).

## Component dependency matrix

### `live_compare` (Problems 857/20/367)

Required in target repo:

- `analysis/problem857_counting_gateboard.json`
- `analysis/problem20_k3_gateboard.json`
- `analysis/problem367_sharp_gateboard.json`
- `scripts/problem857_ops_board.py`
- `scripts/problem20_ops_board.py`
- `scripts/problem367_ops_board.py`
- `scripts/frontier_status.py`

### `problem857` (discovery profile)

Required in target repo:

- all `live_compare` dependencies relevant to Problem 857
- `docs/PROBLEM857_COUNTING_OPS_BOARD.md`
- `orchestrator/v2/scopes/problem_857.yaml`
- `orchestrator/problem857_public_spec_check.py`
- `sunflower_lean/`

In `PROBLEM857_SOURCE_MODE=public_repo`, ORP can satisfy these by syncing the public
`sunflower-lean` repo into `sunflower_lean/` and generating the missing ORP bridge
files itself.

### `governance` (mathlib collaboration)

Required in target repo:

- `docs/MATHLIB_SUBMISSION_CHECKLIST.md`
- `docs/MATHLIB_DRAFT_PR_TEMPLATE.md`
- `docs/MATHLIB_ISSUE_VIABILITY_GATE.md`
- `docs/UPSTREAM_PR_LANE.md`
- `analysis/UPSTREAM_PR_PLAN.yaml`
- `scripts/upstream-pr-plan.py`
- `scripts/upstream-pr-lane.sh`
- `scripts/mathlib-issue-viability-gate.py`
- `scripts/mathlib-naturality-snippet.sh`
- `scripts/mathlib-issue-local-gate.sh`
- `scripts/mathlib-tighten-fine-tooth-gate.sh`
- `scripts/mathlib-ready-to-draft-gate.sh`
- `scripts/mathlib-pr-body-preflight.py`

## Recommendation

- Use `catalog` for immediate public adoption.
- Add `live_compare` once board scripts/data exist in target repo.
- Add `problem857` in `public_repo` mode for public `sunflower-lean` adoption, or use starter/private adapters when you need richer host-repo workflow state.
- Add `governance` when those private/workflow dependencies are available.
