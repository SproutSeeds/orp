# ORP Runner Internal Operations

Use this guide for the internal-first rollout of the hosted ORP runner.

Current production note:

- The SSE wake-up route is live on `https://orp.earth` as of March 16, 2026 via Vercel deployment `dpl_EyxVoapbmsHXF795yKoHN9ua1qRm`.
- A live `orp runner work --continuous --transport auto` smoke has already succeeded against production with checkpoint `d6ddb357-ae66-46bb-98ef-4a19169fc59f` and job `49ee5377-a7df-48af-8350-45524f7a6a77`.

## Source of truth

- Session discovery stays Rust-led.
- The ORP CLI is the canonical link/session/runner contract.
- The hosted web app is the queue and lease authority.
- `orp runner work` is the primary worker surface.
- `orp agent work` remains available only as a compatibility path.

## Healthy runner definition

A healthy internal runner should satisfy all of the following:

- `orp auth login` succeeds for the operator account.
- `orp link project bind` has linked the repo to the intended hosted idea/world.
- At least one non-archived linked session exists for the repo.
- One linked session is primary, or the hosted job targets an exact session.
- `orp runner enable` has created a machine identity on the Mac.
- `orp runner sync` succeeds and the hosted admin runners console shows the machine.
- `orp runner work --once` can poll without lease errors.
- `orp runner work --continuous --transport auto` can idle without missing queued work.
- Heartbeats continue while work is running.
- Completed work clears the lease and updates the hosted world/checkpoint state.

## Deployment checklist

1. Apply the latest hosted database migrations.
2. Deploy the hosted web app with the `/api/cli/runner/...` routes enabled.
3. Confirm the admin runners console loads at `/dashboard/admin/runners`.
4. Confirm at least one internal machine can still sign in through the published `orp` CLI.
5. Confirm the Rust desktop app still discovers sessions and mirrors them into CLI link state.
6. After any machine-scoped session-schema change, run `orp runner sync` once on every active internal runner machine so hosted `idea_world_sessions.runner_id` is refreshed before expecting queued jobs to route correctly.

## Internal smoke flow

Run this on one internal machine after deploy:

1. `orp auth login`
2. `orp link project bind --idea-id <idea-id>`
3. `orp link session register --orp-session-id <orp-session-id> --codex-session-id <codex-session-id> --primary`
4. `orp runner enable`
5. `orp runner sync`
6. `orp checkpoint queue --idea-id <idea-id> --json`
7. `orp runner work --once --json`
8. Optionally leave a longer-lived worker running with `orp runner work --continuous --transport auto --json`
9. Confirm the checkpoint response lands in the hosted idea.
10. Confirm `/dashboard/admin/runners` shows:
   - the machine heartbeat
   - the claimed job
   - lease cleared after completion

Latest known-good production smoke:

- Direct SSE probe returned `event: ready` followed by `event: timeout` against `https://orp.earth/api/cli/runner/events/stream`.
- Continuous runner mode with `--transport auto` claimed the queued checkpoint job immediately and completed it successfully.

## Rust desktop smoke harness

For a repeatable non-GUI Rust-side smoke, run the harness in `orp-rust` against the same live ORP CLI contract:

1. Point `ORP_CLI_BIN` at the CLI build you want the Rust app to exercise.
2. Run:
   `cargo run --bin runner_smoke -- --project-root <repo-root> --idea-id <idea-id> --codex-session-id <codex-session-id> --queue-checkpoint-note "<note>" --work-once --agent-work-once`
3. Confirm:
   - `runner_work.claimed = true`
   - `runner_work.ok = true`
   - `agent_work.compatibility.mode = runner-primary`
   - `agent_work.claimed = false` once the queued job has already been consumed

## Admin console workflow

Use `/dashboard/admin/runners` to:

- inspect online and stale machines
- inspect queued, dispatched, and running jobs
- watch the top-level operational alerts for stale leases, missing sessions, stale heartbeats, and repeat retries
- spot missing-routeable-session issues
- spot stale leases
- spot repeated retry patterns
- cancel a stuck job
- requeue a failed or stale job

## Recovery playbook

Use these defaults unless there is a clearer incident-specific reason to do otherwise:

- If a job is `running` or `dispatched` with an expired lease, requeue it.
- If a job is clearly invalid or targeting the wrong repo/session, cancel it.
- If the same job has been retried 3+ times, pause and inspect the runner, session link, and prompt payload before requeueing again.
- If a machine is stale, verify the desktop app or CLI runner is still open before requeueing its work.
- If jobs queue up with no routeable session, repair the project/session link first instead of repeatedly retrying the job.

## Rollout policy

- Start with one internal operator machine.
- Expand to a small set of trusted internal machines after the first full smoke passes.
- Prefer one or a small handful of linked repos per machine during rollout.
- Treat the admin runners console as the operational dashboard for the staged rollout.
- Do not make WebSocket a prerequisite for rollout; polling remains the stable v1 transport and SSE is optional polish on top.
