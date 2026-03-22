# Changelog

This file tracks user-facing ORP CLI releases.

There was no prior in-repo changelog file, so the first formal entry starts
with the currently shipped `v0.4.4` release and summarizes the full release
delta reflected in this repo.

## v0.4.4 - 2026-03-22

This release establishes ORP as a CLI-first governance and hosted-workspace
system, with the Rust app and web app positioned as reflections of the CLI
contract rather than competing sources of truth.

### Added

- Added first-class local repo governance commands:
  - `orp init`
  - `orp status`
  - `orp branch start`
  - `orp checkpoint create`
  - `orp backup`
  - `orp ready`
  - `orp doctor`
  - `orp cleanup`
- Added first-class machine-local linking commands:
  - `orp link project ...`
  - `orp link session ...`
  - `orp link status`
  - `orp link doctor`
- Added first-class runner commands:
  - `orp runner status`
  - `orp runner enable`
  - `orp runner disable`
  - `orp runner heartbeat`
  - `orp runner sync`
  - `orp runner work`
  - `orp runner cancel`
  - `orp runner retry`
- Added runner-first compatibility flow through `orp agent work`.
- Added machine-readable link and runner schemas:
  - `spec/v1/link-project.schema.json`
  - `spec/v1/link-session.schema.json`
  - `spec/v1/runner-machine.schema.json`
  - `spec/v1/runner-runtime.schema.json`
- Added canonical architecture docs:
  - `docs/CANONICAL_CLI_BOUNDARY.md`
  - `docs/ORP_LINK_RUNNER_PLAN.md`
  - `docs/RUNNER_INTERNAL_OPERATIONS.md`
- Added release automation helpers:
  - `scripts/orp-release-smoke.sh`
  - `scripts/npm-prepublish-guard.js`

### Changed

- Reframed ORP around a single CLI with built-in abilities instead of a
  pack-first public story.
- Made the CLI the canonical source of truth for:
  - repo governance state
  - project/session link state
  - runner identity and runtime state
  - hosted workspace routing and lease semantics
- Expanded `orp about --json` and `orp home --json` so agents and UI layers can
  discover governance, linking, runner, and hosted-workspace surfaces directly.
- Updated the README to teach the governance loop explicitly:
  - branch start
  - checkpoint
  - backup
  - validation
  - readiness
- Updated the agent loop documentation to prefer CLI-native checkpoint and
  backup flows over the older helper-script path.

### Hosted Workspace And Runner

- Folded hosted auth and workspace operations into the ORP CLI surface.
- Standardized hosted prompt-job delivery around link/session/runner concepts.
- Added CLI-owned machine sync and worker execution flows for linked projects
  and sessions.
- Added support for runner wake-up via the same runner contract, with the lease
  model remaining canonical.

### Agent-First Git Safety

- Added `orp backup` so agents can checkpoint and safely back up current work to
  a dedicated remote ref instead of merely warning that work is still local.
- Added backup tracking to git runtime history.
- Made governance status surface backup as a next action when local work is
  dirty and remote-aware backup is possible.
- Added a prepublish guard so npm publish now fails if:
  - the git worktree is dirty
  - or the current commit is not already present on a remote branch

### Packaging And Release

- Published npm package `open-research-protocol@0.4.4`.
- Normalized package metadata, including repository URL formatting.
- Hardened release checklists so backup, clean worktree checks, and remote-sync
  checks are part of the documented release flow.

### Verification

- Added or expanded focused test coverage for:
  - governance initialization and status
  - checkpointing and readiness
  - linking and link-health validation
  - runner status, sync, work, cancel, and retry
  - hosted CLI auth and workspace flows
  - npm publish guard behavior
- Release candidate verified with the full Python suite before shipping.
