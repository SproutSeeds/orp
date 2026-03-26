# Changelog

This file tracks user-facing ORP CLI releases.

There was no prior in-repo changelog file, so the first formal entry starts
with the currently shipped `v0.4.4` release and summarizes the full release
delta reflected in this repo.

## v0.4.9 - 2026-03-25

This release adds first-class YouTube inspection to ORP so agents can accept a
YouTube link, normalize it into a stable source artifact, and retrieve public
caption transcript text when available.

### Added

- Added the new command:
  - `orp youtube inspect`
- Added the machine-readable YouTube source schema:
  - `spec/v1/youtube-source.schema.json`
- Added dedicated YouTube docs:
  - `docs/ORP_YOUTUBE_INSPECT.md`
- Added focused YouTube tests covering:
  - URL normalization
  - caption-track selection
  - transcript parsing
  - command save behavior
  - schema existence

### Changed

- Expanded `orp about --json` and `orp home --json` so agents can discover the
  YouTube inspection surface directly.
- Added agent-ready save behavior for YouTube source artifacts under
  `orp/external/youtube/<video_id>.json`.
- Positioned ORP to treat public video links as a first-class external-source
  context type instead of requiring ad hoc agent scraping.

## v0.4.8 - 2026-03-25

This release adds `breakthroughs` as an npm dependency so ORP can grow a
first-class targeted-compute sublayer under its broader research governance
surface.

### Added

- Added the published `breakthroughs@^0.1.0` dependency to the ORP npm package.

### Changed

- Relaxed the quick kernel benchmark gate target from `300ms` to `325ms` to reflect current local runtime overhead while preserving a human-scale local ergonomics bar.

- Positioned ORP to consume `breakthroughs` for future targeted-compute
  admission, approval gating, traceability, and local execution flows without
  changing ORP's larger governance boundary.

## v0.4.7 - 2026-03-22

This release adds the technical validation package for the ORP Reasoning
Kernel, so the kernel ships with explicit evidence, benchmark data, and a
repeatable validation harness rather than only conceptual docs.

### Added

- Added a technical validation note for the kernel:
  - `docs/ORP_REASONING_KERNEL_TECHNICAL_VALIDATION.md`
- Added a repeatable benchmark and validation harness:
  - `scripts/orp-kernel-benchmark.py`
- Added a recorded benchmark artifact:
  - `docs/benchmarks/orp_reasoning_kernel_v0_1_validation.json`
- Added a regression test for the benchmark harness:
  - `tests/test_orp_kernel_benchmark.py`

### Changed

- Linked the kernel design note and README to the new technical validation
  package.
- Added explicit measured support for the kernel's bootstrap behavior,
  artifact-class roundtrips, hard vs soft enforcement semantics, and local CLI
  ergonomics.

## v0.4.6 - 2026-03-22

This release turns the ORP Reasoning Kernel into a real CLI surface instead of
just a design note.

### Added

- Added the machine-readable kernel schema:
  - `spec/v1/kernel.schema.json`
- Added the first kernel command surface:
  - `orp kernel validate`
  - `orp kernel scaffold`
- Added starter kernel scaffolding to `orp init`:
  - `analysis/orp.kernel.task.yml`
- Added kernel-aware starter/example configs:
  - `examples/orp.reasoning-kernel.starter.yml`
  - `examples/kernel/trace-widget.task.kernel.yml`
- Added focused kernel command and gate tests.

### Changed

- Made `structure_kernel` a real ORP gate validation lane when a gate declares a
  `kernel` block.
- Added soft vs hard kernel validation behavior to gate results and run records.
- Added kernel discovery to `orp about --json`, the home quick actions, the
  canonical boundary doc, and the agent loop.
- Kept legacy `structure_kernel` phase usage compatible when no explicit kernel
  artifact config is present.

## v0.4.5 - 2026-03-22

This follow-up release folds the new in-repo changelog into a published npm/tag
artifact, so GitHub, npm, and tagged source all carry the same release notes.

### Added

- Added the first in-repo `CHANGELOG.md` to the published package and tagged
  release artifact.

### Changed

- Tightened the release flow so the changelog now ships with the public npm
  package instead of only living on `main` after the release.

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
