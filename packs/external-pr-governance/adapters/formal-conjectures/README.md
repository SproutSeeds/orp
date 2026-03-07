# formal-conjectures Adapter Notes

This is the first non-mathlib adapter target for the generic `external-pr-governance` pack.

## Current source of truth

- `docs/EXTERNAL_CONTRIBUTION_GOVERNANCE.md`
- In the live `sunflower-coda` host repo, the watch-board artifacts for:
  - `analysis/OSS_ISSUE_WATCHLIST.json`
  - `analysis/OSS_ISSUE_WATCH_STATUS.md`

Recent live examples in the watch board:

- `google-deepmind/formal-conjectures` PR `#2770`
- `google-deepmind/formal-conjectures` PR `#2771`

## Expected adapter responsibilities

- watch and review tracking
- local Lean build/typecheck before PR update
- issue/PR linkage correctness (`Closes #...` when appropriate)
- concise portable PR body/comment hygiene
- draft CI watch if draft mode is used
- ready-for-review decision gate
- maintainer-feedback hardening

## What is not standardized yet

Compared with mathlib, this adapter still needs:

- a dedicated local-first gate script,
- a dedicated ready-to-draft freeze gate,
- a dedicated PR-body preflight gate.

That is the main standardization gap this pack is meant to close.
