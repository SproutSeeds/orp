# ORP hosted workspace contract 2.0

Status: Exact release contract for ORP 0.5. A release verification record must
name the commands and artifacts that demonstrate this contract.

## Authority boundary

The local ORP workspace ledger is the recovery authority. An orp.earth
workspace is an optional, reviewed projection for cross-machine visibility.
Hosted state never becomes authority for Codex threads, goals, native memory,
configuration, permissions, or execution.

The 2.0 hosted model uses dedicated, versioned workspace records. Legacy
workspace blocks embedded in idea notes remain readable only for migration and
compatibility. ORP 0.5 does not write workspace state into idea notes.

## Dedicated resources

The hosted service stores ORP 2.0 data in these resources:

- `orp_workspaces`: ownership, public selector, title, visibility, optional
  linked idea, contract version, and current state version;
- `orp_workspace_snapshots`: immutable, SHA-256-addressed projection payloads
  with monotonically increasing state versions;
- `orp_workspace_events`: append-only, user-scoped timeline summaries; and
- `orp_workspace_backfills`: reversible mappings from legacy idea rows to
  workspace rows created by a migration batch.

Device authorization uses separate `orp_devices`,
`orp_device_authorizations`, and `orp_device_refresh_tokens` resources.
Every workspace lookup is scoped to the authenticated user.

The additive database migration is:

```text
drizzle/migrations/0046_orp_v2_local_first.sql
```

It does not delete or rewrite legacy idea or device-pairing rows.

## Projection schema

Every pushed state conforms to:

```text
spec/v1/hosted-workspace-state-v2.schema.json
```

Required envelope fields are:

- `contract_version: "2.0.0"`;
- a positive, monotonically increasing `state_version`;
- deterministic `snapshot_id`;
- capture and update timestamps;
- `tab_count`;
- an explicit `sync_policy`; and
- one or more tab identity rows.

The server validates the schema, allowlist, exclusions, byte limit, absolute
path boundary, and payload SHA-256 before committing a snapshot. Reusing a
snapshot ID with different bytes fails.

## Explicit allowlist

The default allowlist is empty. A user may opt in to these fields:

```text
workspace.summary
workspace.current_focus
workspace.trajectory
tabs.title
tabs.remote_url
tabs.remote_branch
tabs.linked_idea_id
tabs.linked_feature_id
tabs.activity
tabs.plan_summary
tabs.tasks
```

Remote URLs are accepted only after credential, query-string, fragment, and
protocol checks. Text and task fields are bounded before projection.

These categories are always excluded, regardless of the allowlist:

- absolute paths;
- source files and file contents;
- transcripts and prompts;
- secret values and secret registry metadata;
- resume commands and resume or session IDs;
- Codex or Claude state;
- machine IDs; and
- hostnames.

The CLI and server both enforce this boundary.

## Reviewed sync

`orp workspace sync` is dry-run by default:

```sh
orp workspace sync main --json
orp workspace sync main --allow tabs.title --allow tabs.remote_url --json
```

The preview contains the exact sanitized hosted projection and deterministic
`snapshot_id`. A write requires the current ID:

```sh
orp workspace sync main \
  --allow tabs.title \
  --allow tabs.remote_url \
  --apply \
  --confirm <snapshot_id> \
  --json
```

If no dedicated hosted record exists, the apply step creates one linked to the
resolved idea and then pushes the snapshot. Idea notes remain unchanged.

## Hosted CLI resources

The authenticated CLI surface is:

```text
GET    /api/cli/workspaces
POST   /api/cli/workspaces
GET    /api/cli/workspaces/:id
PATCH  /api/cli/workspaces/:id
GET    /api/cli/workspaces/:id/tabs
GET    /api/cli/workspaces/:id/timeline
POST   /api/cli/workspaces/:id/state
POST   /api/cli/workspaces/:id/events
```

Read routes require `workspaces:read`. Mutation routes require
`workspaces:write`. These dedicated 2.0 routes reject the legacy bearer-token
fallback even while older CLI routes remain available during migration.
Responses use structured JSON errors and sanitized server-side logging.

The web dashboard presents metadata-only workspace cards and the current
allowlisted projection. It does not reconstruct local paths, resume commands,
or Codex state.

## Authentication contract

`orp auth login` starts browser device authorization and opens
`https://orp.earth/device`. The signed-in user reviews the device name and
requested scopes before approval.

- device and user codes expire after 10 minutes;
- access tokens expire after 10 minutes;
- refresh tokens expire after 30 days and rotate on every use;
- refresh-token reuse revokes the token family;
- access tokens validate signature, issuer, audience, type, expiry, device,
  revocation state, and required scope; and
- users can list and revoke their devices.

The CLI stores access and refresh credentials in the macOS Keychain. The local
session JSON contains only non-secret metadata and Keychain coordinates.
Legacy token acceptance is controlled separately during rollout; disabling it
is an explicit production gate.

```sh
orp auth devices --json
orp auth revoke-device <device_id> --json
```

## Legacy backfill and rollback

The backfill is dry-run by default and creates metadata-only workspace rows.
It preserves every source idea and creates no snapshots:

```sh
pnpm orp:workspace-backfill -- --json
pnpm orp:workspace-backfill -- --apply --confirm <plan_id> --json
```

The resulting `batch_id` can be reviewed for rollback. Rollback removes only
empty rows created by that batch and also requires an exact current plan ID:

```sh
pnpm orp:workspace-backfill -- --rollback <batch_id> --json
pnpm orp:workspace-backfill -- \
  --rollback <batch_id> \
  --apply \
  --confirm <rollback_plan_id> \
  --json
```

Rows with snapshots or events are deliberately retained for manual review.

## Service verification

`GET /healthz` proves process liveness. `GET /readyz` verifies database
connectivity and the seven ORP 2.0 tables; it returns HTTP 503 until both are
ready. Neither response includes credentials or database details.
