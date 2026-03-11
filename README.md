# ORP — Open Research Protocol (template pack)

ORP is a **project-agnostic, docs-first, agent-friendly protocol** for doing research (or research-like engineering) with:

- explicit claim levels,
- reproducible verification hooks,
- dispute handling that resolves disagreements by **verification or downgrade** (not argument),
- first-class “failed paths” (dead ends recorded as assets),
- and a non-blocking **Alignment/Polish Log** for optional wording/clarity suggestions.

**Boundary (non-negotiable):** ORP files are **process-only**. They are **not evidence** and must **not** be cited as proof for
results. Evidence lives in your project’s **canonical artifact paths** (data, code, paper, proofs, logs, etc.).

ORP also supports optional, modular **Instruments** for framing inquiry upstream of claims. Instruments are process-only and
verification remains independent of framing. See `modules/instruments/README.md` and `docs/WHY_INSTRUMENTS.md`.

## What’s in this folder

- `AGENT_INTEGRATION.md` — optional: integrate ORP into an AI agent’s primary instruction file
- `llms.txt` — concise discovery guide for LLM and agentic systems
- `PROTOCOL.md` — the protocol to copy into a project
- `INSTALL.md` — how to adopt ORP in an existing repo or start a new project from it
- `docs/AGENT_LOOP.md` — canonical operating loop when an agent is the primary ORP user
- `docs/EXTERNAL_CONTRIBUTION_GOVERNANCE.md` — canonical local-first workflow for external OSS PR work
- `docs/OSS_CONTRIBUTION_AGENT_LOOP.md` — agent operating rhythm for external contribution workflows
- `templates/` — claim, verification, failure, and issue templates
- `examples/` — minimal examples (illustrative, not exhaustive)
- `scripts/` — optional helper scripts (no dependencies beyond standard shell tools)
- `modules/` — optional modules (including Instruments)
- `docs/` — optional docs (including Instruments overview + presentation)
  - includes standardized external PR governance: `docs/EXTERNAL_CONTRIBUTION_GOVERNANCE.md`
  - includes sunflower-coda PR governance mapping: `docs/SUNFLOWER_CODA_PR_GOVERNANCE_MAPPING.md`
- `cone/` — optional process-only context log (agentic handoff/compaction)
- `spec/` — optional v1 runtime draft schemas (packets/config/lifecycle mapping)
- `packs/` — optional downloadable profile packs (domain templates + metadata)

## Product Shape

ORP should feel like one CLI with built-in abilities:

- `workspace` for hosted auth, idea, feature, world, checkpoint, and worker operations
- `discover` for profile-based GitHub scanning and opportunity selection
- `collaborate` for repository collaboration setup and workflow execution
- `erdos` for Erdos-specific data and workflow support
- `report` and `packet` for ORP artifacts

The `pack` layer still exists, but it is now an advanced/internal surface rather
than the main product story.

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

Fresh-directory smoke test:

```bash
mkdir test-orp && cd test-orp
npm i -g open-research-protocol
orp init
orp gate run --profile default
orp packet emit --profile default
orp report summary
find orp -maxdepth 3 -type f | sort
```

What this proves:

- the global `orp` binary resolves,
- running bare `orp` opens the CLI home screen with packs and quick actions,
- the runtime can initialize a repo-local ORP workspace,
- a gate run writes `RUN.json`,
- packet emit writes process metadata to `orp/packets/`,
- and report summary renders a one-page digest from the last run.

Local repo usage still works:

```bash
./scripts/orp -h
```

Agent-first discovery surfaces:

```bash
orp
orp home --json
orp about --json
orp auth login
orp whoami --json
orp ideas list --json
orp world bind --idea-id <idea-id> --project-root /abs/path --codex-session-id <session-id> --json
orp checkpoint queue --idea-id <idea-id> --json
orp agent work --once --json
orp discover profile init --json
orp discover github scan --profile orp.profile.default.json --json
orp collaborate workflows --json
orp collaborate gates --workflow full_flow --json
orp erdos sync --json
orp pack list --json
orp pack install --pack-id erdos-open-problems --json
orp pack fetch --source <git-url> --pack-id <pack-id> --install-target . --json
orp gate run --profile default --json
orp packet emit --profile default --json
orp report summary --json
```

These surfaces are meant to help automated systems discover ORP quickly:

- bare `orp` opens a home screen with repo/runtime status, available packs, and next commands
- `orp home --json` returns the same landing context in machine-readable form
- `orp auth ...`, `orp ideas ...`, `orp world ...`, `orp checkpoint ...`, and `orp agent ...` expose the hosted workspace surface directly through ORP
- `orp discover ...` exposes profile-based GitHub scanning as a built-in ORP ability
- `orp collaborate ...` exposes built-in collaboration setup and workflow execution without asking users to think in terms of separate governance packs
- `llms.txt` gives a concise repo/package map for agents that scan documentation.
- `docs/AGENT_LOOP.md` gives agents one intended operating rhythm instead of leaving them to invent one.
- `docs/DISCOVER.md` explains the portable discovery profile model and scan artifacts.
- `orp about --json` returns machine-readable capability, artifact, schema, and pack metadata.
- Core runtime and pack commands can emit JSON so agents do not need to scrape human text.
- Stable artifact paths make it easy to follow outputs across runs:
- `orp/state.json`
- `orp/artifacts/<run_id>/RUN.json`
- `orp/artifacts/<run_id>/RUN_SUMMARY.md`
- `orp/packets/<packet_id>.json`
- `orp/packets/<packet_id>.md`
- `orp/discovery/github/<scan_id>/SCAN.json`
- `orp/discovery/github/<scan_id>/SCAN_SUMMARY.md`

Release process:

- `docs/NPM_RELEASE_CHECKLIST.md`
- `docs/ORP_PUBLIC_LAUNCH_CHECKLIST.md`
- `.github/workflows/npm-publish.yml` (publishes on `v*` tags)

## Quick start (existing repo)

1. Copy this folder into your repo (recommended location: `orp/`).
2. Link to `orp/PROTOCOL.md` from your repo `README.md`.
3. Customize **Canonical Paths** inside `orp/PROTOCOL.md` to match your repo layout.
4. Use the templates for all new claims and verifications.
5. Optional (agent users): integrate ORP into your agent’s primary instruction file (see `orp/AGENT_INTEGRATION.md`).

## Quick start (new project)

1. Copy this folder into a new project directory.
2. Edit `PROTOCOL.md` to define your canonical paths and claim labels.
3. Start by adding one small claim + verification record using the templates.
4. Optional (agent users): integrate ORP into your agent’s primary instruction file (see `AGENT_INTEGRATION.md`).

**Activation is procedural/social, not runtime:** nothing “turns on” automatically. ORP works only if contributors follow it.

## Optional Runtime Draft (v1)

ORP remains docs-first by default. For teams that want local gate execution and machine-readable packets, there is an optional v1 draft:

- Overview: `docs/ORP_V1_ATOMIC_DISCOVERY_EVOLUTION.md`
- Packet schema: `spec/v1/packet.schema.json`
- Config schema: `spec/v1/orp.config.schema.json`
- Lifecycle mapping: `spec/v1/LIFECYCLE_MAPPING.md`
- Sunflower atomic profile example: `examples/orp.sunflower-coda.atomic.yml`

Minimal CLI skeleton:

```bash
orp auth login
orp ideas list --json
orp world bind --idea-id <idea-id> --project-root /abs/path --codex-session-id <session-id> --json
orp checkpoint queue --idea-id <idea-id> --json
orp agent work --once --json
orp init
orp gate run --profile default
orp packet emit --profile default
orp report summary --run-id <run_id>
orp erdos sync
```

Equivalent local-repo commands are available via `./scripts/orp ...` when developing ORP itself.

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
