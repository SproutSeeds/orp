# ORP Link And Runner Plan

Use this document as the implementation plan for making project linking, session linking, and hosted runner delivery first-class ORP CLI features.

## Goal

Make the npm/CLI package the source of truth for:

- linking a local repo to a hosted ORP idea/world
- linking one or more local ORP sessions to live Codex sessions
- syncing machine/project/session availability to the hosted app
- receiving hosted jobs and routing them to the correct local Codex session

The Rust desktop app should remain the best UX for session discovery, terminal/window management, and local operator flow, but it should rely on the CLI-owned contract instead of maintaining a divergent one.

## Current State

What already exists:

- The CLI already supports project/world binding through `orp world bind`.
- The CLI already supports hosted auth, hosted ideas, hosted world inspection, hosted checkpoint queueing, and a checkpoint-oriented worker surface.
- The Rust app already shells out to `orp world bind` when linking a project.
- The Rust app already has a machine-runner sync and targeted prompt execution model based on linked projects and linked sessions.

What is misaligned:

- The Rust app stores local project/session state in `.orp/...`.
- The CLI stores repo governance state in `orp/` and `.git/orp/runtime.json`.
- Project binding exists as a low-level CLI command, but there is no CLI-owned project/session registry surface yet.
- There are effectively two worker lanes:
  - checkpoint worker lane in the CLI
  - machine-runner prompt lane in the Rust app

## Product Boundary

The CLI should own:

- the machine-readable project link format
- the machine-readable linked session format
- the machine runner sync format
- the hosted runner work loop contract

The Rust app should own:

- desktop UI
- session discovery
- session/window/tab management
- calling the CLI for canonical project/session link operations

## Canonical Concepts

### Linked Project

A linked project is a local repo that is associated with one hosted idea/world.

Required fields:

- `idea_id`
- `project_root`

Important optional fields:

- `idea_title`
- `world_id`
- `world_name`
- `github_url`
- `linked_at_utc`
- `linked_email`

### Linked Session

A linked session is a machine-local ORP session that can route work into a specific Codex session.

Required fields:

- `orp_session_id`
- `label`
- `state`

Important optional fields:

- `codex_session_id`
- `project_root`
- `role`
- `terminal_target`
- `last_active_at_utc`
- `archived`
- `primary`

### Machine Runner

A machine runner is the machine-local worker identity exposed to the hosted app.

Required fields:

- `machine_id`
- `machine_name`
- `platform`
- `runner_enabled`

Important optional fields:

- `last_heartbeat_at_utc`
- `last_sync_at_utc`
- `app_version`
- `linked_email`

### Hosted Job

A hosted job is a transport-agnostic unit of work that can target a project or an exact linked session.

Required fields:

- `job_id`
- `kind`
- `status`

Important optional fields:

- `idea_id`
- `world_id`
- `machine_id`
- `project_root`
- `orp_session_id`
- `codex_session_id`
- `prompt`
- `lease_id`
- `created_at_utc`
- `started_at_utc`
- `finished_at_utc`

## Storage Plan

### Repo-tracked state

Keep repo governance where the CLI already writes it:

- `orp/governance.json`
- `orp/agent-policy.json`
- `orp/HANDOFF.md`
- `orp/checkpoints/CHECKPOINT_LOG.md`
- `orp/state.json`

### Repo-local machine state

Store machine-local link/session data under `.git/orp/link/` so it does not dirty the worktree or leak machine-specific identifiers into git history.

Planned files:

- `.git/orp/link/project.json`
- `.git/orp/link/sessions/<orp_session_id>.json`
- `.git/orp/link/runner.json`
- `.git/orp/link/runtime.json`

### Global machine state

Store cross-repo machine identity in the user config directory:

- `~/.config/orp/machine.json`

### Migration source

Treat the Rust app's `.orp/project.json` and `.orp/sessions/*.json` as import sources during migration, not as long-term canonical storage.

## Planned CLI Surface

### Project link commands

```sh
orp link project bind --idea-id <idea-id> [--idea-title <title>] [--github-url <url>] [--codex-session-id <session-id>] --json
orp link project show --json
orp link project status --json
orp link project unbind --json
```

Behavior:

- `bind` should call the hosted `world bind` flow and write `.git/orp/link/project.json`.
- `show` should print the stored local linked-project record.
- `status` should combine:
  - local stored link
  - hosted world state
  - local repo governance status
  - whether at least one linked session exists
- `unbind` should remove the local link record and optionally leave the hosted world intact unless an explicit hosted unlink is requested later.

### Session link commands

```sh
orp link session discover --json
orp link session register --orp-session-id <orp-session-id> --codex-session-id <codex-session-id> --label <label> [--primary] --json
orp link session list --json
orp link session show <orp-session-id> --json
orp link session set-primary <orp_session_id> --json
orp link session archive <orp_session_id> --json
orp link session unarchive <orp_session_id> --json
orp link session remove <orp_session_id> --json
orp link session import-rust --json
```

Behavior:

- `discover` should find candidate Codex sessions relevant to the current project root.
- `register` should create or update a linked session record under `.git/orp/link/sessions/`.
- `list` should show active plus archived sessions.
- `set-primary` should guarantee only one primary session per linked project.
- `import-rust` should ingest Rust `.orp/sessions/*.json` state into CLI storage.

### Link summary commands

```sh
orp link status --json
orp link doctor --json
```

Behavior:

- `status` should provide a single machine-readable view of linked project, linked sessions, and runner readiness.
- `doctor` should validate stale paths, missing Codex session ids, moved repos, duplicate primaries, and missing hosted auth.

### Runner commands

```sh
orp runner status --json
orp runner enable --json
orp runner disable --json
orp runner sync --json
orp runner work --once --json
orp runner work --continuous --poll-interval 30 --json
orp runner cancel [<job-id>] [--lease-id <lease-id>] --json
orp runner retry [<job-id>] [--lease-id <lease-id>] --json
```

Behavior:

- `status` should report machine runner state plus linked project/session counts.
- `enable` / `disable` should toggle the local runner state.
- `sync` should publish linked projects and linked sessions to the hosted service.
- `work` should poll or subscribe, claim jobs, route work to a selected linked session, append logs/messages, and complete or fail the job.
- `cancel` / `retry` should operate on the local active or most recent lease-aware runner state when explicit ids are omitted.

## File Schemas

Formal schemas live in:

- [link-project.schema.json](/Users/codymitchell/Documents/code/orp/spec/v1/link-project.schema.json)
- [link-session.schema.json](/Users/codymitchell/Documents/code/orp/spec/v1/link-session.schema.json)
- [runner-machine.schema.json](/Users/codymitchell/Documents/code/orp/spec/v1/runner-machine.schema.json)
- [runner-runtime.schema.json](/Users/codymitchell/Documents/code/orp/spec/v1/runner-runtime.schema.json)

Planned file locations and schema usage:

- `.git/orp/link/project.json` -> `spec/v1/link-project.schema.json`
- `.git/orp/link/sessions/<orp_session_id>.json` -> `spec/v1/link-session.schema.json`
- `.git/orp/link/runner.json` -> `spec/v1/runner-machine.schema.json`
- `.git/orp/link/runtime.json` -> `spec/v1/runner-runtime.schema.json`

## Hosted Contract

The hosted runner contract should be transport-agnostic.

Do not couple business logic to polling.

Required lifecycle:

1. `sync`
   - machine publishes linked projects and linked sessions
2. `claim`
   - worker claims one job or receives one via push
3. `start`
   - worker marks the job running
4. `heartbeat`
   - worker renews lease while executing
5. `message` / `log`
   - worker publishes progress
6. `cancel` / `retry`
   - operator or automation can explicitly interrupt or requeue lease-aware work
7. `complete` or `fail`
   - worker posts final result

All lifecycle operations after `claim` should carry the same `lease_id`.

Transport options that should all work with the same contract:

- polling
- SSE
- WebSocket

## First Implementation Slice

Scope:

- establish CLI-owned local linked-project and linked-session storage
- expose project/session status and manipulation commands
- do not replace the Rust machine-runner execution path yet

### Slice 1 Checklist

- [x] Add local link helpers in `cli/orp.py` for:
  - link root resolution
  - reading/writing `.git/orp/link/project.json`
  - reading/writing `.git/orp/link/sessions/*.json`
  - loading and validating schema-compatible records
- [x] Add `orp link project bind`
- [x] Add `orp link project show`
- [x] Add `orp link project status`
- [x] Add `orp link project unbind`
- [x] Add `orp link session register`
- [x] Add `orp link session list`
- [x] Add `orp link session set-primary`
- [x] Add `orp link session archive`
- [x] Add `orp link session remove`
- [x] Add `orp link status`
- [x] Add `orp link doctor`
- [x] Add `orp link session import-rust`
- [x] Add tests for:
  - bind writes project file
  - bind reuses hosted `world bind`
  - session register writes session file
  - exactly one primary session is enforced
  - archive/remove behaviors
  - Rust import reads `.orp/project.json` and `.orp/sessions/*.json`
  - `link status` reports hosted auth / project / session readiness correctly

### Slice 1 Non-goals

- no hosted runner protocol rewrite yet
- no SSE/WebSocket delivery work yet
- no deprecation of Rust session storage yet
- no UI migration yet

### Slice 1 Acceptance Criteria

- A linked project can be created entirely from the CLI.
- One or more linked sessions can be registered entirely from the CLI.
- The Rust app can keep calling `orp world bind`, but also has a documented path to mirror its session state into the CLI registry.
- `orp link status --json` can answer:
  - is this repo linked?
  - what idea/world is it linked to?
  - what sessions are available?
  - which session is primary?
  - is the repo runner-ready?

## Second Implementation Slice

Scope:

- add CLI-owned machine runner identity and sync
- keep transport as polling first

Checklist:

- [x] Add `~/.config/orp/machine.json`
- [x] Add `orp runner status`
- [x] Add `orp runner enable`
- [x] Add `orp runner disable`
- [x] Add `orp runner sync`
- [x] Reuse the Rust app's current sync payload shape for compatibility
- [x] Add tests for runner state persistence and sync payload generation

## Third Implementation Slice

Scope:

- add CLI-owned runner work loop for `session.prompt`

Checklist:

- [x] Add `orp runner work --once`
- [x] Add `orp runner work --continuous`
- [x] Implement claim/start/log/message/complete/fail flow
- [x] Route jobs by:
  - explicit `orp_session_id` first
  - primary linked session second
  - first active linked session with a `codex_session_id` third
- [x] Add lease heartbeat support
- [x] Add tests for selection logic and job completion/failure handling

## Rust App Integration Checklist

- [x] Replace direct hosted link persistence with CLI-owned project link files
- [x] Replace direct session persistence with CLI-owned session link files or mirrored writes
- [x] Call `orp link session register` when adopting or labeling a session
- [x] Call `orp link session archive` when archiving a session
- [x] Call `orp runner sync` when the app's linked-project/session state changes
- [x] Either:
  - keep the current Rust worker temporarily but make it conform to CLI schemas, or
  - replace it with a wrapper around `orp runner work`

## Migration Checklist

- [x] Add `orp link session import-rust`
- [x] Add `orp link import-rust --all`
- [x] Detect `.orp/project.json` and `.orp/sessions/*.json`
- [x] Preserve `world_id`, `idea_id`, `idea_title`, and linked email where available
- [x] Preserve session labels and active/closed state
- [x] Preserve archived and ignored session tracking where possible
- [x] Do not delete Rust files during the initial migration phase

## Remaining Hosted Platform Checklist

The CLI and Rust app now share one client-side project/session/runner contract, but the hosted web app still needs to expose the matching server contract. The remaining work is now a hosted-platform implementation plan rather than more client-side alignment.

### Hosted Contract Alignment

- [x] Add the `/api/cli/runner/...` route family to the hosted app:
  - `POST /api/cli/runner/sync`
  - `POST /api/cli/runner/heartbeat`
  - `GET /api/cli/runner/jobs/poll`
  - `POST /api/cli/runner/jobs/:id/start`
  - `POST /api/cli/runner/jobs/:id/messages`
  - `POST /api/cli/runner/jobs/:id/logs`
  - `POST /api/cli/runner/jobs/:id/complete`
  - `POST /api/cli/runner/jobs/:id/cancel`
  - `POST /api/cli/runner/jobs/:id/retry`
- [x] Extend hosted session state so synced sessions can persist `orp_session_id` in addition to `codex_session_id`.
- [x] Extend hosted job state so the server can persist `lease_id`, `lease_expires_at`, and `last_heartbeat_at`.
- [x] Keep the hosted runner API device-token authenticated, matching the existing CLI workspace routes.

### Hosted Queue Bridge

- [x] Bridge queued idea checkpoints onto the new runner API so existing checkpoint work can flow through `orp runner work`.
- [x] Return runner jobs as prompt-style work items with enough metadata to route by `ideaId`, `worldId`, `projectRoot`, and optional `orpSessionId`.
- [x] On completion, write successful and failed checkpoint responses back into `idea_checkpoint_responses` and checkpoint/job status fields.
- [x] Preserve existing `orp agent work` compatibility until the runner API is proven in production.

### Hosted Lease Hardening

- [x] Add local runner runtime state in `.git/orp/link/runtime.json` for active lease tracking, last job status, and operator events.
- [x] Add lease ids to runner claim/start/heartbeat/complete payloads and persist them across the full job lifecycle.
- [x] Add explicit cancel and retry/requeue endpoints plus CLI handling for those transitions.
- [x] Add stale local lease detection and operator-facing status warnings.
- [x] Add hosted stale-lease expiry and safe job reclamation rules.
- [x] Add server-side start/complete/cancel/retry validation against the active lease and machine id.
- [x] Bind synced hosted world sessions to the syncing runner machine so poll only claims jobs for repos/sessions that machine actually owns.
- [x] Layer SSE wake-up delivery on top of the same lease protocol while keeping polling as the stable fallback/default.
  - Implemented on March 16, 2026.
  - Added hosted `GET /api/cli/runner/events/stream`.
  - Added CLI `--transport auto|poll|sse` for `orp runner work` and `orp agent work`.
  - SSE is used only as a wake-up signal; job claiming still happens through the existing poll/lease flow.
  - Deployed live on March 16, 2026 via Vercel deployment `dpl_EyxVoapbmsHXF795yKoHN9ua1qRm`.
  - Verified direct production SSE stream response on `https://orp.earth/api/cli/runner/events/stream`.
  - Verified a live `orp runner work --continuous --transport auto` smoke by queueing checkpoint `d6ddb357-ae66-46bb-98ef-4a19169fc59f`, claiming job `49ee5377-a7df-48af-8350-45524f7a6a77`, and finishing it successfully.

### Future Hosted Expansion

- [x] Add a first-class hosted enqueue path for generic `session.prompt` jobs beyond checkpoint reviews.
- [x] Keep checkpoint review jobs and prompt jobs on one hosted job system with distinct job kinds.

### Internal Rollout Operations

- [x] Add an internal admin runners console for machine heartbeat, active lease, and last completed/failed work visibility.
- [x] Add internal queue recovery controls for cancel/retry without the original machine lease.
- [x] Add route/helper logging for failed poll/start/complete flows, lease mismatches, missing-routeable-session failures, and repeated retry patterns.
- [x] Surface runner health in the Rust desktop app so operators can see online/syncing/working/error states locally.
- [x] Add an internal rollout and recovery runbook:
  - [RUNNER_INTERNAL_OPERATIONS.md](/Users/codymitchell/Documents/code/orp/docs/RUNNER_INTERNAL_OPERATIONS.md)
- [x] Deploy the hosted runner backend changes to the real internal environment.
- [x] Run a live internal smoke on deployed infrastructure.
  - Completed on March 16, 2026 against `https://orp.earth`.
  - Verified `orp link project bind`, `orp link session register`, `orp runner enable`, `orp runner sync`, `orp checkpoint queue`, `orp runner work --once`, and `orp agent work --once`.
  - Confirmed the production `orp` checkpoint job `78cd459a-fc0b-451b-af06-be2d27379169` completed successfully and produced checkpoint response `41087b8b-9556-4ec1-90c6-eefb69bac585`.
- [x] Add and verify a reusable Rust-side smoke harness for the desktop wrapper path.
  - Implemented at [runner_smoke.rs](/Users/codymitchell/Documents/code/orp-rust/src/bin/runner_smoke.rs).
  - Verified on March 16, 2026 against `https://orp.earth`.
  - Confirmed Rust-side smoke job `853a55f9-b0e5-42f7-8f2f-cdc8db1a354c` completed successfully and produced checkpoint response `6b5aee77-f176-4249-a127-978b987da946`.

### Hosted Verification

- [x] Run route-level unit coverage for the hosted runner API surface.
- [x] Run TypeScript validation for the hosted app after runner changes.
- [x] Run a real disposable Postgres-backed smoke flow:
  - `sync`
  - `enqueue`
  - `heartbeat`
  - `poll`
  - `start`
  - `messages`
  - `logs`
  - `complete`
  - final `poll -> job: null`
- [x] Fix backend issues surfaced by the real smoke flow:
  - `dev_jobs.idea_id` text-to-uuid join mismatch in runner polling/loading
  - `complete` returning terminal success while leaving `dev_jobs.state = running`
- [x] Fix backend issues surfaced by the live internal smoke:
  - queued runner poll was not scoped to the syncing machine's linked world sessions
  - `idea_world_sessions.runner_id` now binds each synced session to its owning runner machine
- [x] Fix CLI compatibility issues surfaced by the Rust-side smoke:
  - `orp agent work` now preserves the caller's `repo_root` when constructing runner-primary compatibility args

## Edge Cases

- repo linked but no sessions registered
- multiple sessions, none primary
- multiple sessions, more than one marked primary
- project moved on disk
- linked world deleted remotely
- hosted account switched
- stale `codex_session_id`
- session archived locally but still referenced by hosted jobs
- no hosted auth while local link files exist
- runner enabled with zero linked projects
- runner enabled with linked projects but zero usable sessions
- Rust `.orp` state and CLI `.git/orp/link` state disagree

## Decision Log

Current decisions:

- Project and session link state should be machine-local and git-ignored by default.
- The CLI should own the canonical project/session/runner contract.
- The Rust app should remain the strongest desktop UX, not the source of truth.
- Transport choice should not change the hosted runner job lifecycle.
- Polling remains the stable v1 transport, and SSE is now available as an optional wake-up layer on the same lease protocol.
- Checkpoint review jobs and generic prompt jobs should share one hosted job system with distinct kinds.
- `orp runner work` is the primary worker surface, while `orp agent work` remains the compatibility path for now.
- Hosted routing should prefer an exact linked session first, then the primary linked session for that repo.
- Session discovery should stay Rust-led for now, with the CLI remaining the canonical registry and runner contract.
- Rollout should stay internal-first and staged.
- WebSocket is still optional future polish, not a prerequisite for the runner contract.
- Production has already proven the SSE wake-up layer with `--transport auto`; it is now polish, not speculation.
