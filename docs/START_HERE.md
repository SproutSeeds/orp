# Start here

ORP 0.5 is a local-first operating layer for project recovery, storage,
checkpoints, credentials, and small context packets. It works without an
account. orp.earth is an optional destination for a reviewed metadata
projection.

## Core rule

ORP process artifacts are not evidence. Canonical evidence stays in the
project's code, data, proofs, papers, logs, and outputs.

Codex remains the authority for its own threads, goals, native memory,
configuration, permissions, and execution. ORP can describe local repository
state to Codex when you explicitly request it; ORP does not take those systems
over.

## Start in 60 seconds

```sh
npm install -g open-research-protocol

cd /path/to/project
orp init
orp config validate --json
orp storage report --json
orp agents audit
orp checkpoint inspect --json
orp workspace create main
orp workspace add-tab main --here --title "current project"
orp workspace tabs main
orp codex context --allow-once --prompt "my exact prompt"
```

This path is local and offline. It does not create a remote, scan Codex
storage, or contact orp.earth.

## 1. Inspect local configuration

```sh
orp config path
orp config show --json
orp config get codex.context_enabled
orp config validate --json
```

Fresh installations use the XDG layout:

- config: `$XDG_CONFIG_HOME/orp`;
- data: `$XDG_DATA_HOME/orp`;
- state: `$XDG_STATE_HOME/orp`; and
- cache: `$XDG_CACHE_HOME/orp`.

The usual defaults are under `~/.config`, `~/.local/share`,
`~/.local/state`, and `~/.cache`. ORP creates owned directories with mode
`0700`, owned files with mode `0600`, and writes registries atomically.

## 2. Understand storage before changing it

```sh
orp storage report --json
orp storage migrate --json
orp storage compact --json
```

All three commands are read-only in their default form. The report scans only
ORP-owned roots and never scans repositories or `~/.codex`.

Migration copies and SHA-256-verifies known legacy files. It retains the source
bytes and refuses conflicting targets. Apply only after reviewing the current
deterministic plan:

```sh
orp storage migrate --apply --confirm <plan_id> --json
```

Compaction selects only expired ORP backups beyond the configured keep count
and expired ORP cache files. It writes and verifies a deterministic archive
before removing reviewed inputs:

```sh
orp storage compact --apply --confirm <plan_id> --json
```

Repository files, proof/results artifacts, Codex data, secret values, and
unclassified legacy files stay outside that scope.

## 3. Initialize repository governance

```sh
orp init
orp agents audit
orp project show --json
orp status --json
```

`orp init` creates or refreshes the local governance surface. It preserves
human-written text outside ORP-managed blocks in `AGENTS.md` and
`CLAUDE.md`. If several projects inherit guidance from one umbrella
directory, configure it deliberately:

```sh
orp agents root set /absolute/path/to/projects
orp agents sync
orp agents audit
```

`orp project refresh --json` updates the local project lens after material
roadmap, spec, instruction, documentation, manifest, or command changes.

## 4. Create a local workspace ledger

```sh
orp workspace create main
orp workspace add-tab main --here --title "current project"
orp workspace list
orp workspace tabs main
```

Workspace paths and optional resume metadata remain local. If a workspace was
loaded from orp.earth, an add/remove edit creates a local managed copy and
reports `hostedSyncRequired: true`. The edit itself does not write remotely.
`orp workspace list` stays offline; use `orp workspace list --hosted` for one
explicit merged lookup.

Older local resume-command features remain available for users who intentionally
need them. They are not included in hosted projections.

## 5. Give Codex bounded context

The adapter is disabled by default. A one-shot invocation is:

```sh
orp codex context --allow-once --prompt "my exact prompt"
```

For an agent or script:

```sh
printf '%s' "my exact prompt" | \
  orp codex context --allow-once --prompt-stdin --json
```

The adapter:

- reads only documented local repository authority surfaces;
- stays offline and read-only;
- preserves the prompt byte-for-byte;
- emits provenance hashes rather than file contents;
- excludes absolute paths, transcripts, resume IDs, secret values, and all
  Codex-owned state; and
- fails instead of truncating or rewriting when the packet would exceed 2,048
  bytes.

A user may opt in persistently through ORP's own local configuration:

```sh
orp config set codex.context_enabled true
```

This changes ORP configuration only. It does not edit global Codex
configuration. Historical ORP session inspection and launcher behavior requires
`--legacy-session-access`; bare `orp codex` performs no launch or mutation.

## 6. Store credentials locally

On macOS:

```sh
orp secrets add \
  --alias openai-primary \
  --label "OpenAI Primary" \
  --provider openai
```

ORP prompts for the value. Agents use stdin:

```sh
printenv OPENAI_API_KEY | \
  orp secrets add \
  --alias openai-primary \
  --label "OpenAI Primary" \
  --provider openai \
  --value-stdin
```

Then inspect or resolve it:

```sh
orp secrets list --json
orp secrets show openai-primary --json
orp secrets resolve openai-primary --reveal
```

Values live in the macOS Keychain through the native Security.framework API.
The ORP registry contains non-secret metadata only. The public CLI does not
accept plaintext through `--value`.

`keychain-*` commands are compatibility aliases for the same local store.
`orp secrets sync-keychain <alias>` is an explicit one-way import from the
legacy hosted secret API; it is not part of the normal local flow.

## 7. Checkpoint intentionally

```sh
orp checkpoint inspect --json
orp hygiene --json
orp checkpoint create -m "describe the completed unit" --json
```

Inspection is local and read-only. Creation refuses to stage while hygiene
contains unclassified paths. ORP never resets, checks out, or deletes work to
make a tree look clean.

Exact and Verified project claims need a verification hook and a durable
verification record. A failed verification is recorded and the claim is
downgraded.

## 8. Opt in to hosted workspace metadata

Authenticate through the browser device flow:

```sh
orp auth login
orp whoami --json
orp auth devices --json
```

The browser opens `https://orp.earth/device`, where the signed-in user reviews
the device and requested scopes. The CLI keeps the resulting access and refresh
credentials in the macOS Keychain. Revoke a selected device with
`orp auth revoke-device <device_id>`; revoking the current device also clears
its local Keychain bundle.

Preview a metadata projection:

```sh
orp workspace sync main --json
orp workspace sync main --allow tabs.title --allow tabs.remote_url --json
```

The allowlist defaults to empty. A write requires the exact current
`snapshot_id`:

```sh
orp workspace sync main \
  --allow tabs.title \
  --allow tabs.remote_url \
  --apply \
  --confirm <snapshot_id> \
  --json
```

Hosted sync always excludes absolute paths, source files, transcripts, prompts,
secret values and metadata, resume commands and IDs, Codex state, machine IDs,
and hostnames. Dedicated versioned workspace rows are authoritative for the
hosted projection; idea-note workspace blocks are compatibility reads only.

## Daily loop

```sh
orp home
orp agents audit
orp project show --json
orp workspace tabs main
orp agenda focus
orp opportunities list
orp checkpoint inspect --json
orp status --json
```

Use the additional agenda, connections, opportunities, research, packets,
reports, schedules, and collaboration commands when the project needs them.
Their local artifacts remain subject to the same evidence boundary.

## Agent contract

At the start of material work:

1. Read the applicable `AGENTS.md`, `CLAUDE.md`, and `PROTOCOL.md`.
2. Confirm canonical paths.
3. Run `orp hygiene --json`.
4. Stop expansion if `dirty_unclassified` is present.

Before a checkpoint, handoff, release, or remote side effect:

1. Run the decisive project checks.
2. Run `git diff --check`.
3. Re-run `orp hygiene --json`.
4. Classify or checkpoint every remaining path.

## If you remember nine commands

```sh
orp home
orp init
orp config validate --json
orp storage report --json
orp agents audit
orp workspace tabs main
orp codex context --allow-once --prompt "my exact prompt"
orp checkpoint inspect --json
orp hygiene --json
```

See [LOCAL_FIRST_0.5.md](LOCAL_FIRST_0.5.md) for the exact local contract and
[ORP_HOSTED_WORKSPACE_CONTRACT.md](ORP_HOSTED_WORKSPACE_CONTRACT.md) for the
hosted projection and authentication contract.
