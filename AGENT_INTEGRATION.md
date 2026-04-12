# Agent Integration (Agentic Flow)

If you use an AI agent that reads a **primary instruction Markdown file** (agent-specific; the agent will know the filename),
integrate ORP by adding an **ORP section** to that file.

This makes ORP the agent’s default operating mode: explicit claim levels, reproducible verification, first-class failed paths,
and dispute resolution by verification/downgrade (not debate).

If you are working inside an ORP-governed repo, ORP can also scaffold and maintain the repo's own `AGENTS.md` and
`CLAUDE.md` files:

- `orp init` now scaffolds them if missing and refreshes ORP-managed blocks if they already exist
- `orp agents sync` refreshes the ORP-managed blocks later without replacing surrounding human notes
- `orp agents audit` checks whether those files are still aligned
- `orp agents root set /absolute/path/to/projects` establishes an optional umbrella parent directory so child repos can inherit high-level guidance

## Core Rule

Do not let ORP process scaffolding masquerade as evidence or repository truth.

ORP should keep the agent honest about:

- where ongoing work lives
- whether the repo is in a safe state
- which secret or credential should be used
- where the work sits in the larger frontier
- when a checkpoint should be created

But evidence still lives in canonical project artifacts: code, data, logs, papers, proofs, outputs.

## Minimum Working Loop

If the agent only remembers one ORP loop, it should be this:

1. recover the workspace ledger
   ```bash
   orp workspace tabs main
   ```
2. inspect repo safety
   ```bash
   orp status --json
   ```
3. resolve the right secret
   ```bash
   orp secrets ensure --alias <alias> --provider <provider> --current-project --json
   ```
4. inspect the current frontier
   ```bash
   orp frontier state --json
   ```
5. if the work feels confusing or too large, break it down before moving
   ```bash
   orp mode breakdown granular-breakdown --json
   ```
6. do the next honest move
7. checkpoint it honestly
   ```bash
   orp checkpoint create -m "checkpoint note" --json
   ```

That is the ORP rhythm in one line:

- recover continuity
- inspect repo safety
- resolve access
- inspect context
- break down complexity when comprehension would help
- do the work
- checkpoint it honestly

## Agent discovery surfaces

Before deeper work, agents can discover ORP through three lightweight entry points:

- `docs/START_HERE.md` — canonical human/operator onboarding path for local-first ORP usage.
- `llms.txt` — concise repo/package map for agents that scan docs before acting.
- `orp about --json` — machine-readable tool metadata, stable artifact paths, schemas, and available packs.
- `orp pack list --json` — machine-readable inventory of bundled packs.
- `docs/AGENT_LOOP.md` — canonical ORP operating rhythm for agent-led workflows.

## What to add to your agent’s instruction file

Copy/paste this section into your agent’s main instruction Markdown file:

<!-- ORP:BEGIN -->
## Open Research Protocol (ORP)

**Non-negotiable boundary:** ORP docs/templates are **process-only** and are **not evidence**. Evidence must live in canonical
artifact paths (code/data/proofs/logs/papers).

### Default operating rules

- **Always label claims** as one of: **Exact / Verified / Heuristic / Conjecture**.
- If unsure, **downgrade** rather than overclaim.
- For **Exact/Verified**: include a **Verification Hook** (commands + expected outputs + determinism notes) and produce a
  **Verification Record** with **PASS / FAIL / INCONCLUSIVE**.
- If verification is **FAIL**: **downgrade immediately** and link the failure evidence.
- Treat **failed paths** as assets: record dead ends as a `Failed Path Record` with the blocking reason/counterexample and a
  next hook.
- Resolve disputes by **verification or downgrade**, not argument.

### How to work in an ORP repo

- Before starting: read `PROTOCOL.md` and confirm the project’s **Canonical Paths** are defined.
- When proposing a result: create/update a claim (via `templates/CLAIM.md`) that points to canonical artifacts (not ORP docs).
- When verifying: run the hook and write `templates/VERIFICATION_RECORD.md`.
- When something fails: write `templates/FAILED_TOPIC.md` and link it from the claim/issue.

### Instruments (optional; upstream framing only)

- ORP may include optional Instruments under `modules/instruments/` (e.g., Orbit / Compression / Adversarial).
- Instruments are **process-only** and must not contain evidence/results. Verification remains blind to instruments.
- If an Instrument is used, note it in the claim’s **Instrument (optional)** section (name + parameters explored).

### Protocol sync checks (required)

To prevent drift (especially after **context compaction / summarization**), re-check ORP and re-sync this block:

- at **session start** / **new task**,
- **immediately after any context compaction/summarization**,
- before publishing any **Verified/Exact** claim,
- after pulling/updating ORP files in the repo.

Sync procedure:
1) Find the ORP root directory (the folder containing `PROTOCOL.md`).
2) Ensure this ORP block matches `<ORP_ROOT>/AGENT_INTEGRATION.md` (between `<!-- ORP:BEGIN -->` and `<!-- ORP:END -->`).
3) If out of date, sync it (script or manual):
   - `<ORP_ROOT>/scripts/orp-agent-integrate.sh --sync /path/to/your/agent/instructions.md`

### ORP checkpoint tool (recommended for agent workflows)

Use the checkpoint tool to keep handoffs/compactions honest and to reduce “drift-by-forgetting” before `git commit` / `git push`.

- Command:
  - `<ORP_ROOT>/scripts/orp-checkpoint.sh --sync --agent-file /path/to/your/agent/instructions.md "checkpoint note"`
- Recommended moments:
  - after context compaction/summarization or handoff
  - before `git commit` / `git push`
  - before publishing any **Verified/Exact** claim

This writes a process-only entry to `<ORP_ROOT>/cone/CONTEXT_LOG.md` and reports ORP snippet sync status.

<!-- ORP:END -->

## Optional helper script

If you want an automated insert into a file you specify, use:

```sh
./scripts/orp-agent-integrate.sh --sync /path/to/your/agent/instructions.md
```

To check for drift (no changes), use:

```sh
./scripts/orp-agent-integrate.sh --check /path/to/your/agent/instructions.md
```
