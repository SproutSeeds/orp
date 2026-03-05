# ORP — Open Research Protocol (template pack)

ORP is a **project-agnostic, docs-first protocol** for doing research (or research-like engineering) with:

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
- `PROTOCOL.md` — the protocol to copy into a project
- `INSTALL.md` — how to adopt ORP in an existing repo or start a new project from it
- `templates/` — claim, verification, failure, and issue templates
- `examples/` — minimal examples (illustrative, not exhaustive)
- `scripts/` — optional helper scripts (no dependencies beyond standard shell tools)
- `modules/` — optional modules (including Instruments)
- `docs/` — optional docs (including Instruments overview + presentation)
  - includes sunflower-coda PR governance mapping: `docs/SUNFLOWER_CODA_PR_GOVERNANCE_MAPPING.md`
- `cone/` — optional process-only context log (agentic handoff/compaction)
- `spec/` — optional v1 runtime draft schemas (packets/config/lifecycle mapping)
- `packs/` — optional downloadable profile packs (domain templates + metadata)

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
./scripts/orp init
./scripts/orp gate run --profile default
./scripts/orp packet emit --profile default
./scripts/orp report summary --run-id <run_id>
./scripts/orp erdos sync
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

- Pack docs: `docs/PROFILE_PACKS.md`
- Pack metadata schema: `spec/v1/profile-pack.schema.json`
- Included pack: `packs/erdos-open-problems/`

Render a pack template:

```bash
python3 scripts/orp-pack-render.py --pack packs/erdos-open-problems --list
python3 scripts/orp-pack-render.py --pack packs/erdos-open-problems --template sunflower_live_compare_suite \
  --var TARGET_REPO_ROOT=/path/to/repo --out /path/to/repo/orp.erdos-live-compare.yml
python3 scripts/orp-pack-render.py --pack packs/erdos-open-problems --template sunflower_mathlib_pr_governance \
  --var TARGET_REPO_ROOT=/path/to/repo --out /path/to/repo/orp.erdos-mathlib-pr-governance.yml
python3 scripts/orp-pack-render.py --pack packs/erdos-open-problems --template erdos_problems_catalog_sync \
  --var TARGET_REPO_ROOT=/path/to/repo --var ORP_REPO_ROOT=/path/to/orp --out /path/to/repo/orp.erdos-catalog-sync.yml
```
