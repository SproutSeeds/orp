# Project Protocol (ORP)
**Last updated:** 2026-01-21

ORP is a **process-only** protocol for producing trustworthy results.

**Boundary (non-negotiable):** This document and all ORP templates are **not evidence**. They must not be cited as proof for
results. Evidence must live in your project’s **canonical artifact paths** (code, data, logs, proofs, papers, etc.).

---

## Canonical Paths (Source of Truth)

Every project must define, in concrete paths, where authoritative artifacts live. Edit this list for your repo:

- **Paper/spec (if any):** `paper/`
- **Code:** `src/` (or `core/`, etc.)
- **Analysis/experiments:** `analysis/`
- **Data/artifacts:** `data/`
- **Formal proofs (optional):** `proof/` / `lean/` / `coq/`
- **Runbooks/logs (optional):** `runbooks/` / `logs/`

Rule: **All claims must point to canonical artifacts.** If a claim cannot be tied to a canonical artifact, it is not a claim yet.

---

## Claim Levels

All claims must be labeled as exactly one of:

- **Exact** — proven/certified; independently reproducible with explicit commands and artifacts.
- **Verified** — confirmed for a specific artifact (e.g., a construction, dataset, or run) but not claimed optimal/universal.
- **Heuristic** — strong evidence, not exhaustive.
- **Conjecture** — hypothesis / model / pattern; explicitly unproven.

Default rule: **When unsure, downgrade.**

---

## Artifact Requirements (Minimum)

### Exact claims
Must include a verification hook that another person can run:

- precise command(s),
- inputs (paths, versions),
- outputs (logs, certificates, checksums),
- and a verification record showing PASS.

### Verified claims
Must include:

- the artifact (data/model/etc),
- a verifier script or deterministic procedure,
- and a verification record showing PASS.

### Heuristic / Conjecture
Must include:

- scope and limitations,
- what would upgrade it to Verified/Exact,
- and at least one concrete next hook.

---

## Verification Records (Required for Exact/Verified)

Use `templates/VERIFICATION_RECORD.md`.

**Default dispute action:**
- If verification is **FAIL** → downgrade the claim level immediately.
- If verification is **INCONCLUSIVE** → downgrade by default (or keep the original label but add an explicit “blocked by X” note).

---

## Dispute Workflow (Verifier-first)

If two contributors disagree:

1) The claim owner provides canonical artifacts + commands.
2) A verifier attempts reproduction and writes a verification record.
3) Outcomes:
   - PASS → claim stands at its label.
   - FAIL → claim is downgraded (and linked to the failure record).
   - INCONCLUSIVE → downgrade by default; open a follow-up issue.

Disputes must resolve via **verification or downgrade**, not argument.

---

## Failed Paths (First-class artifacts)

Failures are valuable when they prevent repeated work.

Use `templates/FAILED_TOPIC.md` to record:

- what was tried,
- what failed and why,
- the minimal counterexample / blocking reason,
- and a “next hook” for future attempts.

Suggested naming convention:

- `analysis/FAILED_<topic>.md` (or your repo’s canonical analysis area)

---

## Alignment / Polish Log (Non-blocking; Append-only)

When a verification/audit **PASSES** but yields optional suggestions (wording, clarity, alignment),
record them in an append-only log (recommended path):

- `analysis/ALIGNMENT_LOG.md`

Rules:
- Non-authoritative; non-blocking.
- Must not upgrade claims.
- Must not be cited as evidence.

---

## Roles (Optional, but recommended)

This protocol supports role separation:

- **Explorer** — proposes claims, builds artifacts.
- **Verifier** — reproduces/checks claims; can downgrade labels.
- **Synthesizer** — integrates results into shared structure without introducing new claims.

No maintainer tie-break is required if verification hooks exist and downgrade rules are followed.

---

## Contribution Workflow (default)

If unsure where something belongs, record it at a lower claim level and let verification decide.

1) Write a claim using `templates/CLAIM.md` and put the real content in canonical paths.
2) Run verification and write `templates/VERIFICATION_RECORD.md`.
3) Only then update any shared docs (paper/README) with language matching the claim level.
4) If something fails, record it with `templates/FAILED_TOPIC.md`.
