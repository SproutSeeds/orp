# ORP — Open Research Protocol

Maintained by Fractal Research Group (`frg.earth`).

[![npm version](https://img.shields.io/npm/v/open-research-protocol?color=111111&label=npm)](https://www.npmjs.com/package/open-research-protocol)
[![npm downloads](https://img.shields.io/npm/dm/open-research-protocol?color=111111&label=downloads)](https://www.npmjs.com/package/open-research-protocol)
[![GitHub stars](https://img.shields.io/github/stars/SproutSeeds/orp?style=flat&color=111111&label=stars)](https://github.com/SproutSeeds/orp/stargazers)
[![GitHub issues](https://img.shields.io/github/issues/SproutSeeds/orp?color=111111&label=issues)](https://github.com/SproutSeeds/orp/issues)
[![license](https://img.shields.io/npm/l/open-research-protocol?color=111111&label=license)](./LICENSE)
[![node](https://img.shields.io/node/v/open-research-protocol?color=111111&label=node)](https://www.npmjs.com/package/open-research-protocol)

> Agent-first CLI for workspace ledgers, local governance, secrets, scheduling, packets, reports, and research workflows.

**Links:** [GitHub](https://github.com/SproutSeeds/orp) · [npm](https://www.npmjs.com/package/open-research-protocol) · [frg.earth](https://frg.earth)

ORP is a unified CLI for research and research-like engineering. It helps humans and agents:

- keep a durable workspace ledger
- resolve the right secret
- schedule the next loop
- checkpoint and protect progress
- emit packets and reports
- keep hosted and local state aligned

**Boundary (non-negotiable):** ORP files are process-only. They are not evidence and must not be cited as proof. Evidence lives in canonical project artifacts such as code, data, papers, proofs, and logs.

ORP also supports optional modular **Instruments** for shaping inquiry upstream of claims. Instruments are process-only and do not change the verification boundary. See `modules/instruments/README.md` and `docs/WHY_INSTRUMENTS.md`.

## Watch It Run

A short ORP command-family walkthrough:

![open-research-protocol terminal demo](https://raw.githubusercontent.com/SproutSeeds/orp/main/assets/terminal-demo.gif)

The current animation intentionally uses the same human-facing command surfaces ORP prints in the terminal. It is not a fabricated UI layer. It currently shows ORP from multiple angles:

- `home` for discovery and next actions
- `hosted` for ideas, workspaces, runners, and the control plane
- `secrets` for create-or-reuse plus local Keychain sync
- `workspace` for the hosted + local saved workspace ledger and recovery commands
- `schedule` for recurring Codex jobs
- `governance` for local checkpoints and repo safety
- `planning` for frontier, compute, packet, and report surfaces
- `synthesis` for discover, exchange, collaborate, and YouTube ingestion
- `mode` for optional perspective-shift nudges

Maintainer asset generation:

```bash
npm run render:terminal-demo
```

## Install CLI (npm)

Global install:

```bash
npm i -g open-research-protocol
orp
orp -h
```

Prerequisites:

- Python 3 available on `PATH`
- `PyYAML` in that Python environment (`python3 -m pip install pyyaml`)

Local repo usage still works:

```bash
./scripts/orp -h
```

## Start Here

If you are new to ORP, use one canonical onboarding path:

- [docs/START_HERE.md](docs/START_HERE.md)

That guide now follows the same clearer rhythm we liked in `erdos-problems`:

- a fast `Start In 60 Seconds` path
- a zero-assumption `Beginner Flow`
- a practical `Daily Loop`
- a compact `Minimum Working Loop` for agents and operators
- the checkpoint governance loop in plain English

It walks through:

- `orp init`
- local-first workspace ledgers
- saved Codex and Claude resume commands
- secrets setup
- the checkpoint and governance loop
- optional hosted sync later

## Daily ORP Operating System

If you want the shortest honest map of day-to-day ORP, start here:

```bash
orp
orp home
orp workspace tabs main
orp secrets ensure --alias openai-primary --provider openai --current-project
orp checkpoint create -m "capture loop state"
orp packet emit --profile default
orp report summary
orp frontier state
orp schedule list
orp mode nudge sleek-minimal-progressive
```

That sequence covers discovery, workspace recovery, secret resolution, governance, artifacts, planning, automation, and perspective-shift support.

The shorter rule is:

- recover the workspace
- inspect repo safety
- resolve the right secret
- inspect the current frontier
- do the next honest move
- checkpoint at honest boundaries

## Secrets Quick Start

Today, ORP secrets use the hosted ORP secret inventory as the canonical store, with optional local macOS Keychain caching. That means the real first step for secrets is:

```bash
orp auth login
```

After that, there are two normal ways to save a secret.

For a human at the terminal, use the interactive path:

```bash
orp secrets add --alias openai-primary --label "OpenAI Primary" --provider openai
```

ORP then prompts:

```text
Secret value:
```

That is where you paste the real key.

For an agent or script, use stdin:

```bash
printf '%s' 'sk-...' | orp secrets add --alias openai-primary --label "OpenAI Primary" --provider openai --value-stdin
```

After that:

```bash
orp secrets list
orp secrets show openai-primary
orp secrets resolve openai-primary --reveal
```

If you want the convenience command, `ensure` means:

```text
use this saved key if it already exists, otherwise prompt for it and save it
```

So this command:

```bash
orp secrets ensure --alias openai-primary --provider openai --current-project
```

does not contain the key itself. It means:

- look for a saved secret called `openai-primary`
- if it exists, reuse it
- if it does not exist, prompt for the key and save it
- attach it to the current project if needed

For secrets, the simplest plain-English rule is:

- `orp secrets add ...` = save a new key
- `orp secrets list` = see what is saved
- `orp secrets show ...` = inspect one saved key record
- `orp secrets resolve ...` = get the key value for use right now
- `orp secrets ensure ...` = use the saved key if it exists, otherwise create it
- `orp secrets sync-keychain ...` = keep a secure local Mac copy too

You can ignore `--env-var-name` at first. It is optional metadata like `OPENAI_API_KEY`, not the key itself.

## Product Map

Think of ORP as one CLI with a few major lanes:

- `home`, `about`, `mode`, `update`, `maintenance`
  Discovery, status, creativity overlays, and ORP self-upkeep.
- `auth`, `ideas`, `world`, `workspaces`, `checkpoint queue`, `runner`, `agent`
  Hosted control-plane operations.
- `workspace`, `secrets`, `schedule`
  Workspace ledger recovery, API-key management, and recurring Codex jobs.
- `init`, `status`, `branch`, `checkpoint create`, `backup`, `ready`, `doctor`, `cleanup`
  Local repo governance and safe operator flow.
- `packet`, `report`, `frontier`, `compute`
  Structured artifacts, planning, and bounded compute control.
- `discover`, `exchange`, `collaborate`, `youtube`, `erdos`
  Scanning, synthesis, workflow scaffolding, external source ingestion, and domain-specific support.

The `pack` layer still exists, but it is now an advanced/internal surface rather than the main product story.

For agents and machine integrations, the `--json` variants remain the canonical structured interface. The public demo and launch materials use the human-facing command output on purpose so the walkthrough matches what a person actually sees.

## Command Families

Landing and discovery:

```bash
orp
orp home --json
orp about --json
orp mode list --json
orp mode show sleek-minimal-progressive --json
orp mode nudge sleek-minimal-progressive --json
orp update --json
orp maintenance status --json
```

Hosted control plane:

```bash
orp auth login
orp whoami --json
orp ideas list --json
orp workspaces list --json
orp workspaces show <workspace-id> --json
orp checkpoint queue --idea-id <idea-id> --json
orp runner work --once --json
orp agent work --once --json
```

Local desk and automation:

```bash
orp workspace create main-cody-1
orp workspace list
orp workspace tabs main
orp workspace add-tab main --path /absolute/path/to/project --resume-command "codex resume <id>"
orp workspace remove-tab main --path /absolute/path/to/project
orp workspace sync main
orp secrets list --json
orp secrets ensure --alias openai-primary --provider openai --current-project --json
orp secrets sync-keychain openai-primary --json
orp schedule add codex --name morning-summary --prompt "Summarize this repo" --json
```

For secrets, the simplest plain-English rule is:

- `orp secrets ensure ...` = use the saved key if it already exists, or ask for it and create it if it does not
- `orp secrets resolve ...` = return the actual key value for use right now
- you can ignore `--env-var-name` at first; it is optional metadata, not the key itself

Local governance:

```bash
orp init
orp status --json
orp branch start work/<topic> --json
orp checkpoint create -m "describe completed unit" --json
orp backup -m "backup current work" --json
orp ready --json
orp doctor --json
orp cleanup --json
```

Artifacts, planning, and compute:

```bash
orp packet emit --profile default --json
orp report summary --json
orp frontier state --json
orp frontier roadmap --json
orp frontier checklist --json
orp compute decide --input orp.compute.json --json
orp compute run-local --input orp.compute.json --task orp.compute.task.json --json
```

Scanning, synthesis, and collaboration:

```bash
orp discover github scan --profile orp.profile.default.json --json
orp exchange repo synthesize /path/to/source --json
orp collaborate workflows --json
orp collaborate run --workflow full_flow --json
orp youtube inspect https://www.youtube.com/watch?v=<video_id> --json
orp erdos sync --json
```

## Life Ops Bridge

ORP and Life Ops are meant to connect, but they are not the same package.

- `open-research-protocol` stays the main ORP CLI/runtime surface.
- `@lifeops/core` is the Life Ops SDK for normalized agenda items, outreach, and structured share-email drafting.
- `@lifeops/orp` is the bridge package that turns ORP JSON surfaces into Life Ops-compatible items and share-ready project input.

The bridge package lives at `packages/lifeops-orp/`.

## Key Docs

- `docs/START_HERE.md` for the canonical step-by-step starter path
- `AGENT_INTEGRATION.md` for integrating ORP into an agent's primary instructions
- `INSTALL.md` for adopting ORP in an existing repo or new project
- `docs/AGENT_LOOP.md` for the intended operator rhythm
- `docs/AGENT_MODES.md` for optional creativity and perspective overlays
- `docs/EXCHANGE.md` for repository/project synthesis
- `docs/CANONICAL_CLI_BOUNDARY.md` for CLI, Rust, and web responsibility boundaries
- `docs/ORP_HOSTED_WORKSPACE_CONTRACT.md` for the first-class hosted workspace model
- `docs/LAUNCH_KIT.md` for public positioning, demo flow, and launch copy
- `docs/NPM_RELEASE_CHECKLIST.md` and `docs/ORP_PUBLIC_LAUNCH_CHECKLIST.md` for release execution
- `llms.txt` for concise agent/LLM discovery

Stable artifact paths:

- `orp/state.json`
- `orp/artifacts/<run_id>/RUN.json`
- `orp/artifacts/<run_id>/RUN_SUMMARY.md`
- `orp/packets/<packet_id>.json`
- `orp/packets/<packet_id>.md`
- `orp/discovery/github/<scan_id>/SCAN.json`
- `orp/discovery/github/<scan_id>/SCAN_SUMMARY.md`

## Quick start (existing repo)

1. Copy this folder into your repo (recommended location: `orp/`).
2. Link to `orp/PROTOCOL.md` from your repo `README.md`.
3. Customize **Canonical Paths** inside `orp/PROTOCOL.md` to match your repo layout.
4. Run `orp init` in the repo root to establish ORP governance.
5. Use `orp status`, `orp branch start`, `orp checkpoint create`, and `orp backup` as the default implementation loop.
6. Use the templates for all new claims and verifications.
7. Optional (agent users): integrate ORP into your agent’s primary instruction file (see `orp/AGENT_INTEGRATION.md`).

## Quick start (new project)

1. Copy this folder into a new project directory.
2. Run `orp init` immediately so the repo starts ORP-governed.
3. Edit `PROTOCOL.md` to define your canonical paths and claim labels.
4. Start implementation on a work branch with `orp branch start`.
5. Create regular checkpoint commits with `orp checkpoint create`.
6. Use `orp backup` whenever you want ORP to capture current work to a dedicated remote backup ref.
7. Validate promotable task/decision/hypothesis artifacts with `orp kernel validate <path> --json`.
8. Start by adding one small claim + verification record using the templates.
9. Optional (agent users): integrate ORP into your agent’s primary instruction file (see `AGENT_INTEGRATION.md`).

**Activation is procedural/social, not runtime:** nothing “turns on” automatically. ORP works only if contributors follow it.

## Optional Runtime Draft (v1)

ORP remains docs-first by default. For teams that want local gate execution and machine-readable packets, there is an optional v1 draft:

- Overview: `docs/ORP_V1_ATOMIC_DISCOVERY_EVOLUTION.md`
- Packet schema: `spec/v1/packet.schema.json`
- Config schema: `spec/v1/orp.config.schema.json`
- Kernel schema: `spec/v1/kernel.schema.json`
- Lifecycle mapping: `spec/v1/LIFECYCLE_MAPPING.md`
- Sunflower atomic profile example: `examples/orp.sunflower-coda.atomic.yml`
- Kernel starter example: `examples/orp.reasoning-kernel.starter.yml`

Minimal CLI skeleton:

```bash
orp auth login
orp youtube inspect https://www.youtube.com/watch?v=<video_id> --json
orp ideas list --json
orp world bind --idea-id <idea-id> --project-root /abs/path --codex-session-id <session-id> --json
orp checkpoint queue --idea-id <idea-id> --json
orp runner work --once --json
orp runner work --continuous --transport auto --json
orp agent work --once --json   # compatibility alias with legacy checkpoint fallback
orp init
orp status --json
orp branch start work/<topic> --json
orp checkpoint create -m "describe completed unit" --json
orp kernel validate analysis/orp.kernel.task.yml --json
orp backup -m "backup current work" --json
orp gate run --profile default
orp ready --json
orp packet emit --profile default
orp report summary --run-id <run_id>
orp erdos sync
```

Equivalent local-repo commands are available via `./scripts/orp ...` when developing ORP itself.

Kernel helper surfaces:

```bash
orp kernel scaffold --artifact-class task --out analysis/trace-widget.kernel.yml --json
orp kernel validate analysis/trace-widget.kernel.yml --json
```

Run summaries are one-page markdown reports generated from `RUN.json` and intended for fast teammate review:

- what ran,
- what passed/failed,
- where evidence logs live,
- and how reproducible the run is.

Sample summaries:

- `examples/reports/sunflower_live_compare_857.RUN_SUMMARY.md`
- `examples/reports/sunflower_live_compare_20.RUN_SUMMARY.md`
- `examples/reports/sunflower_live_compare_367.RUN_SUMMARY.md`

## Optional Profile Packs

ORP supports reusable domain profile packs so core runtime stays general.

The main public collaboration story is now the built-in `orp collaborate ...`
surface. Treat packs as advanced/internal packaging structure unless you are
working on ORP itself or installing domain-specific workflows like `erdos`.

Built-in collaboration quickstart:

```bash
orp collaborate init
orp collaborate workflows --json
orp collaborate gates --workflow full_flow --json
orp collaborate run --workflow full_flow --json
```

- Pack docs: `docs/PROFILE_PACKS.md`
- Pack metadata schema: `spec/v1/profile-pack.schema.json`
- Included pack: `packs/erdos-open-problems/` (857/20/367 + catalog sync + governance profiles)
- Included pack: `packs/external-pr-governance/` (generic external OSS contribution workflow pack)
- Included pack: `packs/issue-smashers/` (opinionated external contribution workspace pack built on the same governance ideas)

If you are using ORP normally, prefer:

- `orp collaborate ...` for collaboration
- `orp erdos ...` for Erdos work

Reach for `orp pack ...` when you are doing advanced installs, ORP maintenance,
or direct domain-template work.

Pack installation is pack-owned: `pack.yml` can describe installable
components, default includes, dependency checks, and report naming. That lets
ORP consume repo-owned external packs through `--pack-path` without baking
domain-specific install rules into ORP core.

Install pack configs into a target repo (recommended):

```bash
orp pack list

orp pack install \
  --pack-id erdos-open-problems
```

Fetch an external pack repo and install through CLI (no manual clone flow required):

```bash
orp pack fetch \
  --source https://github.com/example/orp-packs.git \
  --pack-id erdos-open-problems \
  --install-target .
```

This writes rendered configs and a dependency audit report at:

- `./orp.erdos-catalog-sync.yml`
- `./orp.erdos-live-compare.yml`
- `./orp.erdos-problem857.yml`
- `./orp.erdos.pack-install-report.md`

Advanced/internal direct install of the Issue Smashers workspace pack:

```bash
orp pack install \
  --pack-id issue-smashers
```

This writes:

- `./orp.issue-smashers.yml`
- `./orp.issue-smashers-feedback-hardening.yml`
- `./orp.issue-smashers.pack-install-report.md`
- `./issue-smashers/` workspace scaffold

The pack is intentionally install-and-adapt:

- it creates the workspace layout and starter docs
- it does not auto-clone target repos
- it keeps governance commands as explicit placeholders until you wire in a repo adapter

By default, install includes starter scaffolding for Problems 857/20/367 so `live_compare` runs are install-and-go in a fresh repo.

If you want the Problem 857 lane to pull the real public `sunflower-lean` repo into an empty repo instead of writing starter-only 857 files, use:

```bash
orp pack install \
  --pack-id erdos-open-problems \
  --include problem857 \
  --var PROBLEM857_SOURCE_MODE=public_repo \
  --var PROBLEM857_PUBLIC_REPO_URL=https://github.com/SproutSeeds/sunflower-lean
```

This syncs the public Lean repo into `sunflower_lean/` and generates the ORP-owned 857 bridge files (`analysis/`, `docs/`, `scripts/`, and `orchestrator/`) on top of it.

For public-only adoption (no private sunflower adapters yet):

```bash
orp pack install \
  --pack-id erdos-open-problems \
  --include catalog
```

Clean-room public pack cycle:

```bash
orp pack install \
  --pack-id erdos-open-problems \
  --include catalog

orp --config orp.erdos-catalog-sync.yml \
  gate run --profile erdos_catalog_sync_active

orp report summary
```

This is the simplest end-to-end pack workflow currently validated against the published npm package.

Manual render path (advanced):

```bash
python3 scripts/orp-pack-render.py --pack packs/erdos-open-problems --list
python3 scripts/orp-pack-render.py --pack packs/erdos-open-problems --template sunflower_live_compare_suite \
  --var TARGET_REPO_ROOT=/path/to/repo --out /path/to/repo/orp.erdos-live-compare.yml
python3 scripts/orp-pack-render.py --pack packs/erdos-open-problems --template sunflower_mathlib_pr_governance \
  --var TARGET_REPO_ROOT=/path/to/repo --out /path/to/repo/orp.erdos-mathlib-pr-governance.yml
python3 scripts/orp-pack-render.py --pack packs/erdos-open-problems --template erdos_problems_catalog_sync \
  --var TARGET_REPO_ROOT=/path/to/repo --var ORP_REPO_ROOT=/path/to/orp --out /path/to/repo/orp.erdos-catalog-sync.yml
```
