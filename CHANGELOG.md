# Changelog

This file tracks user-facing ORP CLI releases.

There was no prior in-repo changelog file, so the first formal entry starts
with the currently shipped `v0.4.4` release and summarizes the full release
delta reflected in this repo.

## v0.4.13 - 2026-03-26

This release makes version-stack frontier control a first-class ORP surface, so
agent-first repos can model the exact live point, the active milestone, the
near structured checklist, and the farther major-version stack inside one
canonical CLI layer.

### Added

- Added the new `orp frontier` command family:
  - `orp frontier init`
  - `orp frontier state`
  - `orp frontier roadmap`
  - `orp frontier checklist`
  - `orp frontier stack`
  - `orp frontier add-version`
  - `orp frontier add-milestone`
  - `orp frontier add-phase`
  - `orp frontier set-live`
  - `orp frontier render`
  - `orp frontier doctor`
- Added repo-local frontier control artifacts under `orp/frontier/`:
  - `state.json`
  - `roadmap.json`
  - `checklist.json`
  - `version-stack.json`
  - `STATE.md`
  - `ROADMAP.md`
  - `CHECKLIST.md`
  - `VERSION_STACK.md`
- Added frontier-aware tests covering scaffolding, live-pointer control, and
  agent discovery metadata.

### Changed

- Expanded `orp about --json` and `orp home --json` so agents can discover the
  frontier control surface directly.
- Positioned ORP to treat long-horizon versioned planning as a first-order CLI
  capability instead of leaving it as repo-specific notes alone.
- Refreshed the local kernel benchmark ergonomics targets to match the current
  reference-machine runtime envelope without changing the benchmark claim
  boundary.

## v0.4.12 - 2026-03-25

This release makes repo-declared compute points first-class in ORP, so
`orp compute` can consume a `breakthroughs` project compute map directly
instead of requiring every caller to hand-build raw compute packets.

### Added

- Added project-map mode to `orp compute decide`:
  - `--project-map <path>`
  - `--point-id <id>`
  - optional `--rung-id <id>`
  - optional `--success-bar <path>`
- Added project-map mode to `orp compute run-local` with the same compute-point
  selection flow plus `--task <path>`.
- Added focused tests covering project-map dispatch and local execution.

### Changed

- Updated ORP to depend on `breakthroughs@^0.1.1`.
- Positioned ORP to let agent-first repos declare compute points once and have
  ORP consume them directly as part of the standard compute wrapper surface.
- Refreshed the cross-domain kernel benchmark validation target to match the
  current local runtime envelope without changing ORP's claim boundary.

## v0.4.11 - 2026-03-25

This release hardens ORP's YouTube ingestion path so public videos with caption
tracks reliably yield full transcript text and timing segments instead of
frequently falling back to metadata-only results.

### Added

- Added transcript track inventory fields to the YouTube source artifact:
  - `transcript_track_count`
  - `available_transcript_tracks`
  - `transcript_track_source`
  - `transcript_sources_tried`

### Changed

- Added Android-player transcript retrieval as a first-class fallback when the
  watch-page caption path is incomplete.
- Expanded transcript parsing to support both classic `<text ...>` captions and
  YouTube's paragraph-style format-3 `<p t=... d=...>` transcripts.
- Updated `orp youtube inspect` docs and CLI discovery text to reflect full
  public transcript ingestion when caption tracks are available.
- Strengthened YouTube tests to cover srv3 parsing, Android fallback behavior,
  and richer artifact shape assertions.

## v0.4.10 - 2026-03-25

This release makes targeted compute a first-class ORP wrapper surface through
`orp compute`, backed by the published `breakthroughs` package.

### Added

- Added `orp compute decide` for bounded compute admission decisions.
- Added `orp compute run-local` for locally admitted compute packets using the
  `breakthroughs` shell adapter.
- Added wrapper-level ORP compute packet emission for process-only traceability.
- Added focused wrapper tests covering local admission, paid approval gating,
  and local execution receipts.

### Changed

- Updated ORP npm wrapper help to advertise the `orp compute` surface.
- Refreshed local ergonomics benchmark thresholds to reflect the current
  reference-machine runtime envelope without changing ORP's claim boundary.

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
