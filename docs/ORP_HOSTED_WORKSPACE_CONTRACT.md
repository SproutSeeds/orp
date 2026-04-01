# ORP Hosted Workspace Contract

This document defines the first-class hosted workspace model that should
replace the current "workspace JSON embedded inside idea notes" bridge.

## Status

The current implementation in this repo is still bridge-first:

- local workspace state can live in a local workspace manifest JSON file
- hosted workspace state is mirrored into an idea's `notes` field via
  the fenced ` ```orp-workspace ` block
- `orp workspace tabs/add-tab/remove-tab/sync` currently read or update that bridge

This document and the accompanying schemas define the next exact contract so
the web app, hosted backend, and CLI can converge on one durable source of
truth.

## Canonical Source Of Truth

The canonical hosted source of truth should be one hosted workspace record:

- schema: `spec/v1/hosted-workspace.schema.json`
- stable id: `workspace_id`
- one current state object
- one activity timeline made of workspace events

Idea notes are a compatibility bridge only after this contract lands.

## Resource Model

### Hosted Workspace

One hosted workspace record owns:

- `workspace_id`
- `title`
- `description`
- `visibility`
- `linked_idea`
- `state`
- `latest_event`
- `metrics`

The important invariant is:

- `state` is the thing ORP opens locally
- the timeline explains how that state changed over time

### Current State

`state` is the exact recoverable workspace ledger shape:

- current tab order
- repo/project roots
- saved `codex resume ...` or `claude --resume ...` commands
- current focus
- current trajectory
- ledger metadata such as host, notes bridge status, and last sync origin

### Timeline Events

Events are append-only and explain why the current state changed:

- workspace created
- ledger viewed
- tab added/removed/updated
- focus summary updated
- trajectory summary updated
- bridge synced back to an idea

Schema:

- `spec/v1/hosted-workspace-event.schema.json`

## CLI Contract

To avoid colliding with the existing local launcher surface under
`orp workspace ...`, the hosted first-class resource should live under:

```bash
orp workspaces ...
```

### Hosted Workspace Commands

List hosted workspaces:

```bash
orp workspaces list [--json]
```

Show one hosted workspace:

```bash
orp workspaces show <workspace-id> [--json]
```

Create one hosted workspace:

```bash
orp workspaces add --title "ORP Main" [--idea-id <idea-id>] [--json]
```

Update one hosted workspace:

```bash
orp workspaces update <workspace-id> [--title <title>] [--description <text>] [--visibility <visibility>] [--json]
```

Show just the current tabs for one hosted workspace:

```bash
orp workspaces tabs <workspace-id> [--json]
```

Show the hosted timeline:

```bash
orp workspaces timeline <workspace-id> [--limit <n>] [--json]
```

Append a new hosted snapshot/state push:

```bash
orp workspaces push-state <workspace-id> --state-file <path> [--json]
```

Append an agent/user event:

```bash
orp workspaces add-event <workspace-id> --event-file <path> [--json]
```

## Local Ledger Bridge Contract

The existing local workspace surface should evolve like this:

Inspect the hosted workspace ledger through the local operator surface:

```bash
orp workspace tabs --hosted-workspace-id <workspace-id>
```

Append or remove ledger entries directly:

```bash
orp workspace add-tab --hosted-workspace-id <workspace-id> --path /absolute/path/to/project --resume-command "codex resume <id>"
orp workspace remove-tab --hosted-workspace-id <workspace-id> --path /absolute/path/to/project
```

Compatibility bridge back to the linked idea when needed:

```bash
orp workspace sync <idea-id> --workspace-file ./workspace.json
```

The long-term rule is:

- `orp workspace ...` remains the local operator surface for editing and inspecting the workspace ledger
- `orp workspaces ...` becomes the hosted source-of-truth surface

## Hosted API Contract

The hosted backend should expose these CLI-facing routes:

```text
GET    /api/cli/workspaces
POST   /api/cli/workspaces
GET    /api/cli/workspaces/:workspaceId
PATCH  /api/cli/workspaces/:workspaceId
GET    /api/cli/workspaces/:workspaceId/tabs
GET    /api/cli/workspaces/:workspaceId/timeline
POST   /api/cli/workspaces/:workspaceId/state
POST   /api/cli/workspaces/:workspaceId/events
```

### GET /api/cli/workspaces

Returns a list view for the web app dropdown and agent discovery:

- `workspace_id`
- `title`
- `linked_idea`
- `metrics`
- `updated_at_utc`
- `latest_event`

### GET /api/cli/workspaces/:workspaceId

Returns the full hosted workspace record conforming to:

- `spec/v1/hosted-workspace.schema.json`

### GET /api/cli/workspaces/:workspaceId/tabs

Returns a thin projection of the current state for lightweight inspection:

- current ordered tabs
- path/project root
- saved resume command or structured resume metadata
- focus/trajectory excerpts

### GET /api/cli/workspaces/:workspaceId/timeline

Returns newest-first hosted workspace events conforming to:

- `spec/v1/hosted-workspace-event.schema.json`

### POST /api/cli/workspaces/:workspaceId/state

Accepts a new current-state payload and:

- validates the incoming state
- increments `state.state_version`
- updates `updated_at_utc`
- appends a `snapshot.created` event

### POST /api/cli/workspaces/:workspaceId/events

Accepts one explicit event payload and appends it to the timeline.

## Web App Contract

The web app should surface hosted workspaces as a first-class screen.

### Workspace List Screen

The list screen should show:

- workspace title
- linked idea title
- tab count
- project count
- current focus
- last updated timestamp
- latest event summary

This is the dropdown/picker surface the user asked for.

### Workspace Detail Screen

The detail page should show:

- workspace header and linked idea
- current summary / focus / trajectory
- ordered tabs with repo roots and session ids
- per-tab focus summary
- per-tab trajectory summary
- current task per tab/project
- timeline of state changes over time

### Timeline

The timeline should make it easy to answer:

- what changed
- when it changed
- whether a tab was added or removed
- what the agent says is being worked on now
- where the work appears to be heading

## Agent Write Contract

Agents should be allowed to update structured workspace state rather than only
free-form notes.

The minimum agent-owned fields are:

- workspace-level `state.summary`
- workspace-level `state.current_focus`
- workspace-level `state.trajectory`
- per-tab `current_task`
- per-tab `focus_summary`
- per-tab `trajectory_summary`

Agents should also append explicit timeline events when they make meaningful
updates so the hosted detail page remains explainable instead of silently
mutating.

## Migration Rule

Migration should happen in this order:

1. create hosted workspace records linked to existing ideas
2. copy the current ` ```orp-workspace ` block into `state`
3. keep mirroring back into idea notes temporarily
4. update the local launcher to prefer `--hosted-workspace-id`
5. make idea-note mirroring optional and eventually secondary

## Non-Negotiable Rule

After the hosted workspace model lands, the web app should never invent a
different workspace state shape from the CLI contract. The CLI contract and
these schemas remain authoritative.
