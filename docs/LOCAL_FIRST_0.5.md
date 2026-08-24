# ORP 0.5 local-first contract

Status: Exact release contract. The verification record for a release candidate
must link the commands and artifacts that demonstrate each implemented item.

ORP 0.5 treats the local machine as the authority for workspace recovery,
configuration, checkpoints, secret lookup, and optional Codex context. Hosted
ORP receives only a reviewed, explicitly allowlisted workspace projection.

## Local configuration

The machine-local configuration is JSON at:

```text
$XDG_CONFIG_HOME/orp/config.json
```

When `XDG_CONFIG_HOME` is unset, the path is `~/.config/orp/config.json`.
Fresh installations use `xdg-v1`. Existing installations with material in the
legacy `~/.config/orp` layout remain on `legacy-v0` until migration is applied.
Automation that redirects only `XDG_CONFIG_HOME` also remains on `legacy-v0` so
it cannot spill files into the real user's data, state, or cache directories.

```sh
orp config path
orp config show --json
orp config get codex.context_enabled
orp config set codex.context_enabled true
orp config validate --json
```

`storage.layout` is read-only through `orp config set`. The migration command is
the only supported way to change it.

## Storage ownership

| Category | XDG root | Examples | Retention |
| --- | --- | --- | --- |
| Config | `$XDG_CONFIG_HOME/orp` | `config.json`, `agents.json` | retained |
| Data | `$XDG_DATA_HOME/orp` | workspaces, schedules, opportunity boards, secret metadata | retained |
| State | `$XDG_STATE_HOME/orp` | maintenance, runner machine state, launch runtime, auth metadata | retained until explicitly replaced |
| Cache | `$XDG_CACHE_HOME/orp` | reproducible cache entries | 30 days by default |

ORP-owned user directories are mode `0700`; ORP-owned user files are mode
`0600`. JSON and workspace-registry writes use a same-directory temporary file,
flush it, and atomically rename it into place.

`orp storage report` scans only ORP-owned roots. It does not scan repositories
or `~/.codex`.

```sh
orp storage report --json
orp storage migrate --json
orp storage compact --json
```

Migration is copy-and-verify. It preserves every legacy source file, reports
unknown files, refuses conflicting targets, and prints a deterministic
`plan_id`. Applying it requires that exact current ID:

```sh
orp storage migrate --apply --confirm <plan_id> --json
```

Rollback is a reviewed edit of the private local `config.json` that restores
`storage.layout` to `legacy-v0`. The migration leaves every legacy byte in
place, so switching the selector back does not require deleting migrated files.

Compaction is dry-run by default. It considers only expired ORP backups beyond
the configured keep count and expired ORP cache files. It creates a
deterministic gzip/tar archive, verifies every archived SHA-256, and only then
removes reviewed source files. Applying requires the exact current plan ID:

```sh
orp storage compact --apply --confirm <plan_id> --json
```

Repository source, proof/results artifacts, Codex storage, secret values, and
unclassified legacy files are outside compaction scope.

## Workspace contract

Workspace create, list, tab editing, and recovery remain local and work without
an account. Editing a workspace that originated on hosted ORP writes a local
managed copy and reports `hostedSyncRequired: true`; it does not mutate the
remote record.

`orp workspace list` reads only the local ledger by default. Use
`orp workspace list --hosted` for one explicit merged lookup, or set
`sync.enabled=true` in local configuration when hosted reads should remain
enabled.

Hosted synchronization uses workspace contract `2.0.0`. It is a dry-run by
default and exposes the exact `snapshot_id` that must be confirmed:

```sh
orp workspace sync main --json
orp workspace sync main --allow tabs.title --apply --confirm <snapshot_id> --json
```

The default allowlist is empty. Supported allowlist fields are:

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

Absolute paths, source-file contents, transcripts, secret values, prompts,
resume commands, resume IDs, Codex state, machine IDs, and hostnames are always
excluded. Older idea-note workspace mirrors are read for compatibility but are
never written by the 0.5 sync path. New syncs use dedicated versioned workspace
records.

## Checkpoint contract

`orp checkpoint inspect --json` is read-only and local-only. It reports the Git
boundary and hygiene classification without reading file contents. Checkpoint
creation contacts no hosted service and refuses to stage when hygiene reports
unclassified paths:

```sh
orp checkpoint inspect --json
orp checkpoint create -m "describe completed unit" --json
```

The checkpoint commit and ORP checkpoint log remain canonical repository
artifacts.

## Codex contract

Codex owns its threads, goals, native memory, configuration, permissions, and
execution. ORP 0.5 does not alter those systems as part of its context adapter.

The adapter is disabled by default. A user can enable it in local configuration
or opt in for one invocation:

```sh
orp codex context --allow-once --prompt "my exact prompt"
printf '%s' "my exact prompt" | orp codex context --allow-once --prompt-stdin
```

The adapter:

- is read-only and offline;
- never opens `~/.codex`, a rollout, a transcript, memory, goals, or permission state;
- preserves the supplied prompt byte-for-byte;
- emits repository state and hashes of local contract files as provenance;
- emits no absolute path or resume ID;
- never performs hosted sync; and
- rejects the request instead of truncating or rewriting the prompt if the full
  packet would exceed the configured size, with a hard maximum of 2,048 bytes.

The historical session-status, reconcile, and launcher commands remain only as
explicit compatibility surfaces. Each invocation requires
`--legacy-session-access`. Bare `orp codex` performs no launch or mutation.

## Secret boundary

Ordinary secret commands are local by default:

```sh
orp secrets add --alias openai-primary --label "OpenAI Primary" --provider openai
printenv OPENAI_API_KEY | \
  orp secrets add --alias openai-primary --label "OpenAI Primary" \
  --provider openai --value-stdin
orp secrets list --json
orp secrets show openai-primary --json
orp secrets ensure --alias openai-primary --provider openai --current-project
orp secrets resolve openai-primary --reveal
orp secrets update openai-primary --value-stdin
orp secrets archive openai-primary
```

Values remain in the macOS Keychain. ORP files contain only aliases, provider
labels, optional usernames, bindings, status, and spend-policy metadata. The
generic command surface does not accept a plaintext `--value` argument; humans
use the hidden prompt and agents use stdin so secret bytes do not appear in the
process argument list.

Keychain reads and writes call macOS Security.framework directly. ORP does not
launch the `security` command with credential arguments or pipe credential
bytes through its subprocess input path. This preserves long credentials
without the truncation behavior seen in the command-line utility.

`keychain-add`, `keychain-list`, and `keychain-show` remain compatibility
aliases for the same local store. `sync-keychain` is the one explicit legacy
path: it imports a selected value from the old hosted secret API into the local
Keychain after hosted authentication. New local secret commands never upload
values or registry metadata.

Hosted access and refresh credentials use the same Keychain boundary. The local
auth-state file stores only the service/account locator and non-secret session
metadata. Secret commands currently require macOS; the rest of ORP remains
cross-platform.
