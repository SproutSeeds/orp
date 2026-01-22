# Agent Integration (Agentic Flow)

If you use an AI agent that reads a **primary instruction Markdown file** (agent-specific; the agent will know the filename),
integrate ORP by adding an **ORP section** to that file.

This makes ORP the agent’s default operating mode: explicit claim levels, reproducible verification, first-class failed paths,
and dispute resolution by verification/downgrade (not debate).

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
