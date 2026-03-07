# External Contribution Governance

Date: 2026-03-07

This document explains how ORP should represent external OSS contribution work such as:

- contributing from a local research repo into `leanprover-community/mathlib4`
- contributing into `google-deepmind/formal-conjectures`
- contributing into any other upstream repo where etiquette, coordination, and review discipline matter

It is the ORP-side entry point for PR-governance workflow design.

## What This Document Is

This is not a mathlib document, a formal-conjectures document, or a repo-specific checklist.

It is the ORP contract for external contribution workflow:

- what ORP should standardize
- what should stay adapter-specific
- what lifecycle an agent or operator should preserve
- how to keep governance artifacts process-only while real evidence stays in the working repo

If someone asks, "How should ORP model external PR work without hardcoding one ecosystem's rules?",
this is the document they should read first.

## What ORP Is Standardizing

ORP should standardize:

- lifecycle states for external contribution work
- machine-readable gate outcomes
- packet and summary structure for governance runs
- the boundary between process metadata and evidence
- the adapter model for ecosystem-specific commands and etiquette

ORP should not hardwire:

- one project's PR-body wording
- one project's branch naming rules
- one project's build commands
- one project's disclosure or queue policy
- one project's social norms as if they were universal protocol semantics

Those belong in adapters, rendered configs, or host-repo docs.

## Boundary

ORP remains process-only.

- ORP docs, packets, summaries, and governance reports are not evidence.
- Evidence remains in canonical artifact paths of the working repo.
- Governance profiles track workflow quality, review discipline, and readiness state.
- They do not prove mathematical truth or replace host-repo verification artifacts.

This matters because external contribution work often mixes:

- real repo evidence such as test logs, proof artifacts, CI results, and source diffs
- process coordination such as overlap checks, PR readiness, draft CI watch, and review-thread handling

ORP is responsible for the second category and should point clearly at the first.

## When To Use This

Use this governance layer when the primary task is:

- selecting upstream work
- coordinating with an existing contributor
- validating whether a PR is appropriate to open
- moving from local branch to draft PR
- deciding whether a draft is truly ready for review
- responding to maintainer feedback in a disciplined loop

Do not use this document as the main guide for:

- pure research-claim verification
- theorem/proof evidence review
- repo-internal task orchestration that does not involve upstream etiquette

## First Read

Read these in order:

1. `docs/EXTERNAL_CONTRIBUTION_GOVERNANCE.md`
2. `PROTOCOL.md`
3. `AGENT_INTEGRATION.md`
4. `docs/AGENT_LOOP.md`
5. `docs/OSS_CONTRIBUTION_AGENT_LOOP.md`
6. `docs/SUNFLOWER_CODA_PR_GOVERNANCE_MAPPING.md`
7. the current host-repo handoff or contribution-governance notes

Use the current `sunflower-coda` workflow as the reference implementation, but do not copy its
repo-specific details into ORP core semantics.

## Standard Lifecycle

This is the portable lifecycle ORP should represent.

1. `watch_and_select`
   Identify a contribution target and confirm it is worth pursuing.
2. `viability_gate`
   Check whether the issue or idea is actually appropriate for contribution.
3. `overlap_and_coordination`
   Avoid duplicating active work and coordinate before competing.
4. `isolated_local_work`
   Work in an isolated branch or worktree.
5. `local_first_verification`
   Prefer local validation before spending CI or reviewer attention.
6. `ready_to_draft_freeze`
   Pause, tighten, and confirm the branch is genuinely ready to be shown.
7. `draft_pr_open_or_update`
   Open or update the PR in draft state first.
8. `draft_ci_watch`
   Watch draft CI and fix issues before promotion.
9. `ready_for_review_decision`
   Promote only when the full gate chain is satisfied.
10. `feedback_hardening_loop`
   Convert maintainer feedback into concrete fixes and new guards when possible.

This lifecycle is the heart of the ORP representation.

## Generic Rules To Preserve

These are the portable norms the ORP side should preserve across ecosystems.

1. Coordinate before competing with an active contributor.
2. Prefer local verification over CI churn.
3. Open or update PRs as draft first.
4. Keep public PR text portable and concise.
5. Only mark ready for review when the full gate chain is satisfied.
6. Resolve review threads only after the corresponding fixes are pushed and rechecked.
7. Thank reviewers directly and specifically after fixes land.
8. When maintainer feedback reveals a missed check, convert it into a guard if machine-checkable.

## Where This Lives In ORP

The intended ORP layout is:

- canonical governance doc:
  - `docs/EXTERNAL_CONTRIBUTION_GOVERNANCE.md`
- operator-facing loop:
  - `docs/OSS_CONTRIBUTION_AGENT_LOOP.md`
- generic pack root:
  - `packs/external-pr-governance/`
- adapters:
  - `packs/external-pr-governance/adapters/mathlib/`
  - `packs/external-pr-governance/adapters/formal-conjectures/`
- generic profile templates:
  - `packs/external-pr-governance/profiles/oss-pr-governance.yml.tmpl`
  - `packs/external-pr-governance/profiles/oss-feedback-hardening.yml.tmpl`
- illustrative example:
  - `examples/orp.external-pr-governance.yml`

## Reference Implementation

Right now, the strongest live reference implementation is in `sunflower-coda`.

Treat these as the model for behavior, not as ORP-core files to copy directly:

- host-repo docs for submission checklist, viability gate, PR template, feedback loop, and upstream lane
- host-repo analysis artifacts for issue watchlists and watch status
- host-repo scripts for viability, overlap, local gate, tighten, ready-to-draft, PR opening, and PR-body preflight

ORP's job is to extract the generic shape from that implementation without freezing `sunflower-coda`
details into core semantics.

## What Belongs Where

Use this split when porting an external contribution workflow into ORP.

### ORP core

Belongs here:

- generic lifecycle semantics
- packet/report schema
- machine-readable run outcomes
- process/evidence boundary

Does not belong here:

- mathlib-specific branch naming
- formal-conjectures-specific build commands
- repo-specific PR templates
- repo-specific queue policy text

### Generic governance pack

Belongs here:

- generic pre-open, local-readiness, draft-lifecycle, and feedback-hardening profiles
- generic variable names
- generic gate naming
- generic lifecycle ordering

### Adapters

Belongs here:

- exact commands
- exact pass tokens
- exact host-repo file paths
- exact etiquette overlays that are specific to one ecosystem

### Host repo

Belongs here:

- actual source changes
- actual test and verification artifacts
- actual PR text and issue references
- actual evidence and reviewer-visible outputs

## Definition Of Done

Use this checklist to decide whether the ORP-side port is actually complete.

### Coverage

- `PASS` if the ORP workflow covers:
  - watch
  - viability
  - overlap
  - local gate
  - ready-to-draft
  - draft PR
  - draft CI
  - ready-for-review
  - feedback hardening

### Separation

- `PASS` if ORP core remains generic.
- `FAIL` if ecosystem-specific rules leak into ORP core semantics.

### Contracts

- `PASS` if decisions and gate outcomes are machine-readable.
- `PASS` if lifecycle states map cleanly into ORP `workflow_state`.

### Etiquette

- `PASS` if the ORP representation preserves:
  - coordination-first behavior
  - draft-first behavior
  - no-ready-before-green
  - concise public replies
  - review-thread discipline

### Validation

- `PASS` if the ORP side includes at least:
  - one mathlib example run
  - one formal-conjectures example run
  - one blocked or coordinate-first example
  - one full green local-to-ready chain

### Hardening

- `PASS` if the ORP port explicitly requires:
  - missed check -> new guard when machine-checkable
  - docs/template/instruction update in the same pass
  - PASS + FAIL evidence for the new guard behavior

## Recommended Next Move

Treat mathlib as the reference implementation and formal-conjectures as the first non-mathlib
adapter.

The next ORP implementation step should be:

1. define the generic external-contribution pack contract
2. keep the existing mathlib implementation as the reference adapter
3. add a formal-conjectures adapter with the same lifecycle shape
4. only then tighten prompts and operator instructions around it
