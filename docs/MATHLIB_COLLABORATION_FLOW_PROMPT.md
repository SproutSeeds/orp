# ORP Agent Prompt, Mathlib Collaboration Flow

You are onboarding into ORP with no prior chat context.

Goal:
Encode a proven, local-first mathlib collaboration workflow into ORP in a way that is reusable, auditable, and maintainer-friendly.

## Primary source of truth to ingest first

Read these files from this path:
`/path/to/sunflower-coda/repo`

- `docs/MATHLIB_SUBMISSION_CHECKLIST.md`
- `docs/MATHLIB_ISSUE_VIABILITY_GATE.md`
- `docs/MATHLIB_DRAFT_PR_TEMPLATE.md`
- `docs/MATHLIB_NATURALITY_SNIPPET.md`
- `docs/WORKTREE_LANES.md`
- `scripts/mathlib-issue-local-gate.sh`
- `scripts/mathlib-issue-viability-gate.py`
- `scripts/mathlib-overlap-precheck.sh`
- `scripts/mathlib-pr-body-preflight.py`
- `scripts/install-mathlib-local-hook.sh`
- `scripts/issue-watch.py`
- `analysis/OSS_ISSUE_WATCHLIST.json`
- `analysis/OSS_ISSUE_WATCH_STATUS.md`

## Non-negotiable constraints

1. ORP docs/templates are process, not evidence.
2. Evidence remains in canonical artifact paths, packets only reference those paths.
3. Local-first gateing comes before draft CI.
4. Coordination-first etiquette applies for assigned or already-active issues.
5. Public PR text must be concise and portable, never machine-local.
6. No auto-merge behavior, ORP standardizes evidence and reviewability.

## Required mathlib flow to represent in ORP

### A. Pre-work viability and overlap gates

- Viability decisions must include:
  - `PASS`
  - `COORDINATE`
  - `CLOSE_CANDIDATE`
  - `BLOCKED_NOT_OPEN`
- Include overlap precheck against open PRs before drafting.
- Require a natural-generality check before implementation.

### B. Local implementation gates

- Branch naming includes issue number.
- Targeted build and targeted linter run.
- Local gate runner is canonical pass/fail decision.
- Support local-hold mode where work remains local with no draft PR.

### C. Draft and review lifecycle

Use this lifecycle exactly:
`local_green -> draft_open -> draft_ci_green -> ready_for_review`

Track at least:
- action owner
- last checked timestamp
- last reviewed timestamp
- work stage
- whether review is needed

### D. PR body hygiene gate

Require:
- concise summary
- portable validation wording
- no absolute local paths
- no machine-only helper commands in public PR text

## What to produce in ORP

1. A proposal to update ORP positioning language to:
   `spec-first core, optional runtime, optional profiles`
   while preserving current protocol guarantees.
2. ORP schema mapping for collaborator states and gate outcomes.
3. A mathlib profile config with command mappings for the gates above.
4. A minimal runtime plan that wraps existing scripts first.
5. Migration notes from current scripts to ORP profile adapters.
6. A short risk register with mitigations.

## Delivery format

Return all of the following:

1. Proposed repo tree changes.
2. Profile schema snippet.
3. State machine table.
4. Sample packet JSON that references canonical evidence paths.
5. Phased rollout plan:
   - Phase 1: spec + profile
   - Phase 2: runtime wrappers
   - Phase 3: reviewer/collaborator UX modules

## Decision defaults

Unless blocked, default to:
- Language: TypeScript/Node for v1 CLI speed
- Config: `orp.yml` with explicit gate command contracts

If you propose a different default, include a concrete tradeoff table.

## Scope discipline

- Do not redesign ORP from scratch.
- Preserve ORP epistemic boundaries from `PROTOCOL.md`.
- Keep MVP small, local-first, deterministic.
- Optimize for maintainers adopting the least-scary slice first.
