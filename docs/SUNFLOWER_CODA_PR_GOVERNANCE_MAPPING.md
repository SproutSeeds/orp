# Sunflower-Coda PR Governance Mapping (ORP)

Date analyzed: 2026-03-05

For the generalized cross-ecosystem version, read:

- `docs/EXTERNAL_CONTRIBUTION_GOVERNANCE.md`

This note maps live `sunflower-coda/repo` PR-governance flow into ORP profile-pack gates without hardwiring ORP core to one team.

## Sources reviewed

- `docs/MATHLIB_SUBMISSION_CHECKLIST.md`
- `docs/MATHLIB_ISSUE_VIABILITY_GATE.md`
- `docs/MATHLIB_DRAFT_PR_TEMPLATE.md`
- `docs/UPSTREAM_PR_LANE.md`
- `docs/UPSTREAM_SCOUT_LOOP.md`
- `scripts/mathlib-issue-viability-gate.py`
- `scripts/mathlib-issue-local-gate.sh`
- `scripts/mathlib-tighten-fine-tooth-gate.sh`
- `scripts/mathlib-ready-to-draft-gate.sh`
- `scripts/mathlib-pr-body-preflight.py`
- `scripts/upstream-pr-lane.sh`
- `scripts/upstream-pr-plan.py`

## Live contract extracted

- Viability decision contract:
  - `PASS`, `COORDINATE`, `CLOSE_CANDIDATE`, `BLOCKED_NOT_OPEN`
  - gate output key: `decision=<...>`
- Queue policy contract (anti-spam):
  - `policy.submission_mode=<...>`
  - `policy.max_prs_per_session=<...>`
  - `policy.require_explicit_approval=<...>`
- Local gate contract:
  - `gate=PASS`
  - marker output: `marker_file=...`
- Tighten gate contract:
  - `tighten_fine_tooth=PASS`
- Ready-to-draft contract:
  - `ready_to_draft=PASS`
- PR body preflight contract:
  - `gate=PASS`
  - includes metrics line (`metrics: ...`)

## ORP representation

Added template:

- `packs/erdos-open-problems/profiles/sunflower-mathlib-pr-governance.yml.tmpl`

Profiles:

- `sunflower_mathlib_pre_open`
  - checklist presence
  - queue policy guard
  - lane checklist snapshot
  - issue viability decision
  - naturality snippet
- `sunflower_mathlib_draft_readiness`
  - local issue gate (core build/lint only)
  - tighten/fine-tooth
  - ready-to-draft freeze
  - PR body preflight
- `sunflower_mathlib_full_flow`
  - combined pre-open + draft-readiness gates

## Why this stays general

- ORP core remains unchanged (`spec + runtime + packets`).
- Sunflower/mathlib details live in an optional pack template.
- The same runtime can execute different packs for different ecosystems.
- Runtime inputs are parameterized:
  - `TARGET_REPO_ROOT`, `MATHLIB_REPO_ROOT`, policy defaults
  - per-run env (`ORP_ISSUE_NUMBER`, `ORP_BRANCH_NAME`, `ORP_NATURALITY_MODULE`, `ORP_PR_BODY_FILE`, `ORP_READY_NOTE`)

This keeps ORP broadly reusable while preserving high-rigor local gate behavior for your active workflow.
