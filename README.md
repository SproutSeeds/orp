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
