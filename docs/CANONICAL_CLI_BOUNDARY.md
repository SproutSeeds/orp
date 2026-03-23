# Canonical CLI Boundary

Use this document as the canonical boundary for ORP system ownership.

The npm/CLI package is the source of truth for ORP runtime state and contract
semantics. The Rust desktop app and the web app should reflect that truth, not
replace it.

## Goal

Keep one authoritative ORP contract for:

- local repo governance
- local project/session/runner state
- reasoning-kernel artifact schemas and validation semantics
- hosted auth and hosted workspace operations
- runner delivery, lease, and retry semantics
- machine-readable JSON surfaces for agents and UI layers

This lets ORP work in three modes without changing the underlying model:

- CLI-only
- CLI + Rust desktop UX
- CLI + hosted web UX

## Non-Negotiable Rule

If Rust or web needs a new ORP capability, the canonical behavior should first
exist in the CLI contract.

UI surfaces may:

- rename concepts for clarity
- hide advanced controls
- present minimal or full modes
- automate CLI actions behind the scenes

UI surfaces must not:

- invent a second project/session/runner state model
- redefine lease or routing behavior
- store conflicting link truth outside CLI-owned artifacts
- make "minimal mode" mean a different ORP protocol

## CLI-Owned Domains

The CLI permanently owns these domains.

### 1. Repo Governance

Commands:

- `orp init`
- `orp status`
- `orp branch start`
- `orp checkpoint create`
- `orp backup`
- `orp ready`
- `orp doctor`
- `orp cleanup`

Canonical tracked artifact paths:

- `orp/governance.json`
- `orp/agent-policy.json`
- `orp/HANDOFF.md`
- `orp/checkpoints/CHECKPOINT_LOG.md`
- `orp/state.json`
- `orp/artifacts/<run_id>/RUN.json`

Canonical machine-local runtime path:

- `.git/orp/runtime.json`

### 2. Local Link And Session Registry

Commands:

- `orp link project bind`
- `orp link project show`
- `orp link project status`
- `orp link project unbind`
- `orp link session register`
- `orp link session list`
- `orp link session show`
- `orp link session set-primary`
- `orp link session archive`
- `orp link session unarchive`
- `orp link session remove`
- `orp link status`
- `orp link doctor`

Canonical machine-local artifact paths:

- `.git/orp/link/project.json`
- `.git/orp/link/sessions/*.json`

This registry defines:

- which local repo is linked
- which hosted idea/world it maps to
- which ORP sessions exist locally
- which Codex session id is routable
- which linked session is primary

### 3. Runner Identity And Runtime

Commands:

- `orp runner status`
- `orp runner enable`
- `orp runner disable`
- `orp runner heartbeat`
- `orp runner sync`
- `orp runner work`
- `orp runner cancel`
- `orp runner retry`

Canonical machine-local artifact paths:

- `~/.config/orp/machine.json`
- `.git/orp/link/runner.json`
- `.git/orp/link/runtime.json`

This runtime defines:

- machine identity
- enabled/disabled state
- last heartbeat and sync
- active lease/job state
- retry/cancel bookkeeping

### 4. Hosted Workspace Contract

Commands:

- `orp auth ...`
- `orp ideas ...`
- `orp feature ...`
- `orp world ...`
- `orp checkpoint ...`
- `orp runner ...`
- `orp agent ...`

This is the canonical client for:

- hosted auth/session state
- idea and world binding
- checkpoint queueing
- runner polling/SSE wake-up
- lease/claim/start/complete/cancel/retry behavior

### 5. Reasoning Kernel

Commands:

- `orp kernel validate`
- `orp kernel scaffold`

Canonical schema path:

- `spec/v1/kernel.schema.json`

This surface defines:

- typed promotable artifact classes
- minimum structural completeness rules
- soft vs hard kernel validation semantics
- machine-readable kernel validation results in ORP runs

### 6. Machine-Readable ORP Contract

Preferred discovery surfaces:

- `orp`
- `orp home --json`
- `orp about --json`
- all core stateful surfaces that already support `--json`

If Rust or web needs new structured data, add it to a CLI JSON surface first
instead of scraping human-readable output or inventing a UI-only schema.

## Preferred Product Language

The CLI may keep some lower-level historical names for compatibility, but the
preferred product model should be:

- `Linked Project`
- `Linked Session`
- `Runner`
- `Checkpoint`
- `Project Workspace`

Compatibility surfaces that may remain but should not become the main product
story:

- `orp world bind`
- `orp agent work`

Preferred higher-level story:

- `orp link ...`
- `orp runner ...`
- `orp checkpoint ...`

## Reflection Rules

### Rust Desktop App

Rust should own:

- session discovery
- terminal/window/tab management
- resume/reopen UX
- local operator experience
- background automation of CLI commands

Rust should call into CLI-owned truth for:

- project linking
- session registration
- primary session changes
- runner enable/heartbeat/sync/work

Rust may store desktop-only state such as:

- window placement
- UI preferences
- recent local navigation
- transient discovery caches

Rust should not become canonical for:

- linked project truth
- linked session truth
- runner identity or lease semantics
- hosted sync payload semantics

### Web App

Web should own:

- hosted presentation
- project/session/chat UX
- idea/pensieve browsing UX
- admin/operator visibility

Web should reflect:

- hosted state created or synced through CLI contracts
- linked projects as synced worlds
- linked sessions as hosted-session availability
- runner lifecycle as hosted lease/job state

Web should not invent:

- a second local linking model
- browser-only runner routing rules
- UI-only checkpoint/lease semantics

### Headless / Agent-Only Mode

The system should remain operable without Rust.

Minimum CLI-only flow:

```bash
orp auth login
orp link project bind --idea-id <idea-id> --project-root /abs/path --json
orp link session register --orp-session-id <session-id> --label <label> --codex-session-id <codex-session-id> --primary --json
orp runner enable --json
orp runner sync --json
orp runner work --continuous --transport auto --json
```

That means Rust is an operator UX layer, not a protocol dependency.

## One-To-One Reflection Standard

The best-case stack is:

- CLI defines the truth
- Rust reflects the truth locally
- web reflects the truth remotely

Both Rust and web may expose:

- minimal mode
- full mode
- guided workflows
- hidden advanced controls

Those are presentation choices only. They should all map back to the same CLI
contract.

## Conformance Checklist

Use this checklist whenever Rust or web adds a new ORP capability.

### Before Shipping A New UX Capability

- [ ] The capability exists as a CLI command or JSON surface first.
- [ ] The canonical state path is CLI-owned.
- [ ] The Rust or web implementation can be described as "calling ORP" rather
      than redefining ORP.
- [ ] Any renamed UX language still maps cleanly to existing CLI concepts.

### Rust Conformance

- [ ] Rust does not persist conflicting project/session/runner truth.
- [ ] Rust session discovery ends in `orp link session ...`.
- [ ] Rust project linking ends in `orp link project ...` or approved CLI
      compatibility plumbing.
- [ ] Rust runner background work ends in `orp runner ...`.
- [ ] Rust can be simplified, restyled, or minimized without changing ORP
      semantics.

### Web Conformance

- [ ] Web linked-project pages reflect hosted synced state.
- [ ] Web session/chat views reflect exact linked session identity where
      available.
- [ ] Web does not create a second local-binding protocol.
- [ ] Web operator/admin tooling reflects hosted runner state rather than
      inventing browser-local runner truth.
- [ ] Web can be redesigned completely without requiring a protocol rewrite.

### Protocol Stability

- [ ] CLI-only operation still works.
- [ ] Rust remains optional for correctness.
- [ ] Web remains optional for correctness.
- [ ] Minimal mode and full mode share the same underlying ORP contract.

## Decision Rule For Future Work

When a feature request touches project linking, session identity, runner state,
hosted job delivery, or repo governance:

1. Add or refine the CLI contract first.
2. Expose it through JSON.
3. Let Rust and web reflect it.

If a proposal cannot be expressed cleanly through the CLI first, it is probably
trying to put source-of-truth logic in the wrong layer.

## Short Version

The CLI is ORP.

Rust is the local operator shell.

Web is the hosted operator shell.

Both should be able to become more minimal, more opinionated, or more polished
without changing the underlying ORP truth.
