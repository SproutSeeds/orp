# orp-workspace-launcher

Manage a durable ORP workspace ledger of project paths plus saved `codex resume ...` or `claude --resume ...` commands, optional remote git URLs, bootstrap commands, and per-machine workspace identity.

The package no longer automates iTerm or Terminal.app. The workspace ledger is the source of truth, and you use Terminal however you want.

## Core flow

Create a local workspace ledger with no hosted account required:

```bash
orp workspace create main-cody-1
orp workspace create research-lab --path /absolute/path/to/research-lab --resume-tool claude --resume-session-id 469d99b2-2997-42bf-a8f5-3812c808ef29
orp workspace create mac-main --machine-label "Mac Studio" --path /absolute/path/to/orp --remote-url git@github.com:SproutSeeds/orp.git --bootstrap-command "npm install"
```

Inspect the saved ledger:

```bash
orp workspace ledger main
orp workspace tabs main
```

Print copyable recovery commands:

```bash
orp workspace tabs main
orp workspace tabs main --json
```

Add a new saved tab manually:

```bash
orp workspace ledger add main --path /absolute/path/to/frg-site --resume-command "codex resume 019d348d-5031-78e1-9840-a66deaac33ae"
orp workspace add-tab main --path /absolute/path/to/anthropic-lab --resume-tool claude --resume-session-id claude-456
orp workspace add-tab main --path /absolute/path/to/orp-web-app --remote-url git@github.com:SproutSeeds/orp-web-app.git --bootstrap-command "pnpm install"
```

Remove a saved tab manually:

```bash
orp workspace ledger remove main --path /absolute/path/to/frg-site
orp workspace remove-tab main --resume-session-id claude-456 --resume-tool claude
```

Work directly with a local manifest file:

```bash
orp workspace add-tab --workspace-file ./workspace.json --path /absolute/path/to/orp
orp workspace tabs --workspace-file ./workspace.json
orp workspace tabs --workspace-file ./workspace.json --json
```

Sync a local manifest back to the hosted canonical workspace:

```bash
orp workspace sync main --workspace-file ./workspace.json
orp workspace sync main --workspace-file ./workspace.json --dry-run
```

List saved workspaces:

```bash
orp workspace list
orp workspace slot list
orp workspace slot set main main-cody-1
orp workspace slot set offhand research-lab
```

## Options

- `--json`: print agent-friendly JSON
- `--notes-file <path>`: read a local notes file instead of ORP
- `--hosted-workspace-id <id>`: read or update a first-class hosted workspace instead of an idea-backed bridge
- `--workspace-file <path>`: read or update a structured workspace manifest JSON file
- `--base-url <url>`: override the ORP hosted base URL
- `--orp-command <path-or-command>`: override the ORP CLI binary used to fetch hosted idea JSON
- `--path <absolute-path>`: add or match a saved project path
- `--title <text>`: set or match a saved tab title
- `--remote-url <git-url>`: remember where to clone the repo on another machine
- `--remote-branch <branch>`: remember the branch to clone by default
- `--bootstrap-command <text>`: remember the setup command for another machine, like `npm install`, `pnpm install`, or `uv sync`
- `--resume-command <text>`: save or match an exact `codex resume ...` or `claude --resume ...` command
- `--resume-tool <codex|claude>`: build or narrow the resume command by tool
- `--resume-session-id <id>`: build or match a specific session id
- `--index <n>`: remove a saved tab by 1-based index
- `--all`: remove every matching saved tab

## Cross-machine idea

The local `path` is still the machine-specific working directory. The optional `remoteUrl`, `remoteBranch`, and `bootstrapCommand` fields are the portable part that an agent or user can carry to another rig.

That means one workspace can remember:

- where the repo lives on this machine
- which git remote should be cloned on the next machine
- which setup command should be run after clone
- which `codex resume ...` or `claude --resume ...` line is valid on this machine

Resume session ids are still machine-local/runtime-local. The remote and bootstrap metadata are what make the ledger portable.
