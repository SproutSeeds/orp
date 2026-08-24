# Launch kit

## Positioning

Short version:

ORP is a local-first CLI for workspace recovery, project context, secrets,
checkpoints, and research workflows.

Medium version:

ORP gives people and coding agents one local operating layer for understanding
a repo, recovering a workspace, finding the right credential, checking storage,
and creating an intentional checkpoint. orp.earth adds an optional,
metadata-only workspace view.

Long version:

ORP starts with a practical question: what does an agent need to understand this
project and continue safely? It keeps the answer in local workspace,
configuration, storage, and governance surfaces. It can give Codex a small
prompt-preserving context packet when you ask for one, while Codex keeps
ownership of its threads, goals, memory, permissions, and execution. Hosted
sync is a separate reviewed step with an explicit field allowlist.

Public demos and launch materials should show the command output ORP actually
prints.

## Launch copy

### One-liner

Local-first project context, workspace recovery, secrets, and checkpoints for
people and coding agents.

### Short post

I just shipped ORP 0.5. It is a local-first CLI for project context, workspace
recovery, secrets, checkpoints, and research workflows. It works offline,
keeps credentials in the macOS Keychain, and only sends workspace metadata to
orp.earth when you preview and confirm an allowlisted projection. Install it
with `npm install -g open-research-protocol`.

### Longer post

I just shipped ORP 0.5. The main change is that the local machine is clearly in
charge now. Workspaces, configuration, storage review, checkpoints, and secret
lookup all work without an account. The Codex adapter is optional, read-only,
offline, and capped at 2 KiB. It preserves your prompt and stays out of Codex
threads, goals, memory, permissions, and execution.

orp.earth is still useful when you want the same workspace metadata visible
across machines. That sync starts as a dry run, defaults to an empty allowlist,
and needs the exact snapshot ID before it writes. Paths, source files,
transcripts, prompts, secret values, resume IDs, and Codex state stay local.

## Demo flow

Primary local demo:

```sh
npm install -g open-research-protocol
orp home
orp init
orp config validate --json
orp storage report --json
orp workspace create main
orp workspace add-tab main --here --title "current project"
orp workspace tabs main
orp codex context --allow-once --prompt "my exact prompt"
orp checkpoint inspect --json
```

Focused secrets demo on macOS:

```sh
orp secrets add --alias openai-primary --label "OpenAI Primary" --provider openai
orp secrets list --json
orp secrets show openai-primary --json
```

Focused hosted demo:

```sh
orp auth login
orp whoami --json
orp workspace sync main --allow tabs.title --json
orp workspace sync main --allow tabs.title --apply --confirm <snapshot_id> --json
```

## What to emphasize

- Local work remains useful without an account.
- `workspace tabs main` is the recovery surface.
- Secret values live in the native macOS Keychain and stay out of hosted sync.
- The Codex adapter adds bounded repository context without owning Codex.
- Hosted projection is field-allowlisted, previewed, and exactly confirmed.
- `orp home --json` and `orp about --json` give agents structured discovery.

## GitHub presentation notes

Recommended repo tagline:

Local-first project context, workspace recovery, secrets, and checkpoints for
people and coding agents.

Recommended demo assets:

- animated terminal demo: `assets/terminal-demo.gif`
- poster frame: `assets/terminal-demo-poster.png`
- storyboard grid: `assets/terminal-demo-storyboard.png`
- per-scene posters under `assets/terminal-scene-*.png`

## npm presentation notes

- Keep the README lead readable.
- Show the terminal demo GIF near the top.
- Lead with local setup, storage visibility, workspace recovery, and the bounded
  Codex adapter.
- Introduce hosted sync as an optional reviewed projection.

## Maintainer notes

Regenerate terminal demo assets with:

```sh
npm run render:terminal-demo
```
