# Launch Kit

## Positioning

Short version:
- ORP is an agent-first CLI for research workflows, workspace ledgers, secrets, scheduling, and governed execution.

Medium version:
- ORP is a unified CLI surface for turning a project directory into a reusable agent-friendly operating environment: hosted auth, local governance, saved workspaces, scheduled Codex jobs, secrets, packets, reports, and more.

Long version:
- ORP is meant to feel like one tool that helps operators and agents move from "what am I working on?" to "recover the workspace ledger, resolve the right key, run the next loop, checkpoint the state, and keep the workflow honest." It supports both hosted control-plane flows and local-first repo governance without forcing the user to stitch together a pile of unrelated scripts.

Demo/marketing rule:
- Public demos and launch materials should use the same human-facing command output ORP actually prints. Do not paraphrase command results into friendlier invented summaries.

## Launch Copy

### One-liner
- Agent-first CLI for research workflows, saved workspaces, secrets, and governed execution.

### Short post
- I just shipped `open-research-protocol`, an agent-first CLI for research workflows, saved workspaces, secrets, scheduled Codex jobs, and governed project execution. It is designed to make the local desk and the hosted control plane feel like one surface. Install with `npm install -g open-research-protocol`. GitHub: https://github.com/SproutSeeds/orp

### Longer post
- I just shipped `open-research-protocol`, a unified CLI for agent-first research and research-like engineering. ORP can keep a hosted workspace ledger synced, manage a hosted secret inventory with optional local Keychain sync, schedule recurring Codex jobs, and still expose the local governance loop for checkpoints, packets, reports, and readiness. The goal is not just "more commands"; it is one coherent operator surface that agents can discover and use without losing track of boundaries.

## Demo Flow

Primary demo flow:

```bash
npm install -g open-research-protocol
orp home
orp workspaces list
orp auth login
orp secrets add --alias openai-primary --label "OpenAI Primary" --provider openai
orp workspace tabs main
orp schedule add codex --name morning-summary --prompt "Summarize this repo"
orp checkpoint create -m "capture loop state"
orp frontier state
orp exchange repo synthesize /path/to/source
orp mode nudge sleek-minimal-progressive
```

Focused workspace demo:

```bash
orp workspace list
orp workspace tabs main
orp workspace tabs main
orp workspace add-tab main --path /absolute/path/to/project --resume-command "codex resume <id>"
orp workspace sync main
```

Focused secrets demo:

```bash
orp auth login
orp secrets add --alias openai-primary --label "OpenAI Primary" --provider openai
orp secrets list --json
orp secrets sync-keychain openai-primary --json
orp secrets resolve openai-primary --reveal --local-first --json
```

## What To Emphasize

- One CLI surface instead of a scattered bag of scripts.
- Strong workspace recovery with `workspace tabs main`.
- Interactive secret save for humans, stdin-based save for agents, plus optional local Keychain sync.
- Scheduled Codex work without making the operator wire raw cron jobs.
- Agent-readable discovery surfaces like `orp home --json` and `orp about --json`.

## GitHub Presentation Notes

Recommended repo tagline:
- Agent-first CLI for research workflows, saved workspaces, secrets, and governed execution.

Recommended demo assets:
- animated terminal demo: `assets/terminal-demo.gif`
- poster frame: `assets/terminal-demo-poster.png`
- storyboard grid: `assets/terminal-demo-storyboard.png`
- per-scene posters:
  - `assets/terminal-scene-01-home.png`
  - `assets/terminal-scene-02-hosted.png`
  - `assets/terminal-scene-03-secrets.png`
  - `assets/terminal-scene-04-workspace.png`
  - `assets/terminal-scene-05-schedule.png`
  - `assets/terminal-scene-06-governance.png`
  - `assets/terminal-scene-07-planning.png`
  - `assets/terminal-scene-08-synthesis.png`
  - `assets/terminal-scene-09-mode.png`

## npm Presentation Notes

- Keep the README lead readable.
- Show the terminal demo GIF near the top.
- Use the demo flow to make the command families concrete quickly.
- Prefer the workspace + secrets story over listing every possible ORP surface at once.

## Maintainer Notes

Regenerate the terminal demo assets with:

```bash
npm run render:terminal-demo
```
