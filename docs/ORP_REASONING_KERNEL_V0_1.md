# ORP Reasoning Kernel v0.1

Status: draft

This document defines the first ORP framing for a reasoning kernel that fits
the current CLI-first contract.

## Purpose

The ORP Reasoning Kernel is the artifact-shaping grammar that interprets
intent, validates structure, and governs promotion into canonical repository
truth.

It should make three things true at once:

- humans can speak naturally at the boundary
- agents can reason structurally while operating
- repositories remain canonically legible over time

The kernel is not the repository's source of truth by itself. The repository's
canonical artifacts remain the source of truth. The kernel defines the shape
those artifacts must satisfy before ORP treats them as solid enough to trust,
reuse, test, and hand off.

Short form:

- natural language at the boundary
- kernel structure at promotion
- canonical artifacts at the core

Or even shorter:

- loose in, structured through, solid out

## Why It Belongs In ORP

ORP already has most of the right boundary lines:

- the CLI is the canonical contract
- canonical artifacts are distinct from chat
- packets are process metadata, not evidence
- evidence remains in canonical artifact paths
- `structure_kernel` already exists as a named gate phase in the v1 schemas

That means the kernel should enter ORP as a protocol and artifact discipline,
not as a UI-only idea and not as a parallel chat system.

## Non-Goals

The kernel should not become:

- a mandatory prompt rewriter for every user message
- a style police layer for normal English
- a second truth system outside repository artifacts
- a heavyweight blocker that turns ORP into bureaucracy
- an attempt to define one grand ontology for all human reasoning

ORP should stay fluid at intake and rigorous at promotion.

## Core Model

The kernel should operate across three layers.

### 1. Raw Intent

This is the boundary layer where humans and agents can remain loose.

Examples:

- a chat message
- a checkpoint note
- a bug report
- a design ask
- a quick research hypothesis
- a rough implementation request

Raw intent is allowed to be partial, ambiguous, and exploratory.

### 2. Working Interpretation

This is the agent's kernel-shaped reading of the request. It is structured, but
still revisable.

Examples of working-interpretation fields:

- artifact class
- object
- goal
- boundary
- constraints
- invariants
- failure modes
- evidence expectations
- next action class
- candidate canonical target

This layer is not yet repository truth. It is the agent's current structured
map.

### 3. Canonical Artifact

This is the layer ORP will trust as repository truth.

Examples:

- task card
- design decision
- hypothesis record
- experiment record
- checkpoint summary
- policy object
- result record

Artifacts become canonical only after they satisfy the kernel's typed
completeness rules.

## Kernel Roles

The kernel should have three roles.

### Interpreter

Turn natural language into structured intent.

Example:

- raw ask: "build the trace widget for terminal sessions so I can watch what
  lanes are doing and quickly tell if one is drifting"
- interpreted structure:
  - object: terminal trace widget
  - goal: expose lane state and drift
  - boundary: terminal-first orchestration UX
  - failure mode: hidden drift and unclear status
  - next action: spec then incremental implementation

### Validator

Check whether a proposed artifact is structurally sufficient for its class.

### Canonizer

Govern whether and how accepted work enters canonical repository artifacts.

The kernel does not replace repository truth. It controls the grammar for how
repository truth gets shaped.

## Soft Mode And Hard Mode

This is the most important operating distinction.

### Soft Mode

Used at intake and during ideation.

The kernel may:

- classify the request
- infer missing structure
- surface ambiguity
- suggest what is missing
- route the next action

The kernel should not block the user from speaking naturally.

### Hard Mode

Used when work is promoted into canonical repository artifacts.

If something is going to become:

- a task card
- a design decision
- a hypothesis
- an experiment
- a policy object
- a checkpoint summary
- a stable result record

then it must satisfy the kernel's minimum structural rules for that artifact
class.

This gives ORP the right balance:

- ideation stays fluid
- repository truth stays solid

## Kernel Primitives

These are the first useful cross-artifact fields.

- `artifact_class`
- `object`
- `goal`
- `boundary`
- `constraints`
- `invariants`
- `failure_modes`
- `evidence_expectations`
- `success_criteria`
- `next_action`
- `canonical_target`
- `artifact_refs`

Not every artifact class needs every field. The kernel should be typed.

## Typed Artifact Classes

The kernel should start with a small set of artifact classes rather than trying
to model everything at once.

### `task`

Minimum useful fields:

- object
- goal
- boundary
- constraints
- success_criteria

### `decision`

Minimum useful fields:

- question
- chosen_path
- rejected_alternatives
- rationale
- consequences

### `hypothesis`

Minimum useful fields:

- claim
- boundary
- assumptions
- test_path
- falsifiers

### `experiment`

Minimum useful fields:

- objective
- method
- inputs
- outputs
- evidence_expectations
- interpretation_limits

### `checkpoint`

Minimum useful fields:

- completed_unit
- current_state
- risks
- next_handoff_target
- artifact_refs

### `policy`

Minimum useful fields:

- scope
- rule
- rationale
- invariants
- enforcement_surface

### `result`

Minimum useful fields:

- claim
- evidence_paths
- status
- interpretation_limits
- next_follow_up

## Kernel Operators

These are the actions an agent can take through the kernel.

### Classify

Determine what kind of artifact or action is being requested.

### Expand

Turn shorthand into a fuller structure.

### Tighten

Remove ambiguity and define boundaries more explicitly.

### Challenge

Surface assumptions, missing invariants, or weak success criteria.

### Route

Choose the next action:

- explore
- implement
- critique
- test
- summarize
- ask
- update an artifact

### Promote

Move working interpretation into canonical artifact form.

### Downgrade

If verification or structure fails, lower the claim or keep it provisional.

### Record

Write the appropriate process metadata and artifact references.

## The Kernel Test

The kernel test is the minimum structural truth standard for promotion.

A proposed artifact passes the kernel test when another human or agent can tell:

- what it is
- why it exists
- what boundaries apply
- what assumptions it depends on
- what success or failure would look like
- where its evidence or dependent artifacts live

This should not be one giant universal checklist. It should be a typed test
based on artifact class.

Example:

A proposed task called `Build terminal drift monitor` is not yet solid enough.

Kernel questions:

- what is the object?
- what boundary defines the monitor?
- what signals does it consume?
- what counts as drift?
- what constraints exist?
- what invariants must hold?
- how will success be measured?
- what artifact should this produce?

After expansion:

- object: terminal lane drift monitor
- goal: reveal divergence between intended lane behavior and actual outputs
- inputs: lane logs, timing, state transitions, error events
- outputs: summarized health state and drill-down trace
- constraints: terminal-native, low overhead, no GUI dependency
- invariant: does not alter lane execution
- failure_modes: false positives, information overload, missing event capture
- success_criteria: operator identifies a stalled or drifting lane within ten
  seconds
- canonical_target: monitor spec plus event schema plus sample logs

Now it is structurally legible enough to promote.

## Relationship To Evidence

The kernel does not redefine ORP's evidence boundary.

It should reinforce it.

- packets remain process metadata
- summaries remain process metadata
- kernel traces remain process metadata
- evidence remains in canonical artifact paths such as code, data, papers,
  proofs, logs, and experiment outputs

The kernel governs shape, not proof.

## Relationship To Chat

Chat should not become source of truth by accident.

The correct split is:

- raw conversation is exploratory
- working interpretation is semi-structured
- canonical artifacts are the repository truth

This prevents chat from turning into a mushy, implicit spec layer.

## CLI Integration Points

The kernel should live in the CLI contract, not in UI-only layers.

### 1. `gate`

`structure_kernel` already exists as a gate phase in:

- `spec/v1/orp.config.schema.json`
- `spec/v1/packet.schema.json`

This is the most natural hard-mode enforcement surface.

The first kernel validations should plug in here.

### 2. `checkpoint`

Checkpoint notes may stay natural-language, but ORP should eventually support a
kernel-shaped checkpoint summary for more reliable handoff.

### 3. `packet`

Packets may record kernel validation status and artifact references as process
metadata only.

### 4. `report`

Reports may render kernel-shaped summaries for human review, but should not
pretend that kernel structure is evidence.

### 5. `ready`

Where readiness depends on canonical artifact quality, ORP may eventually
require kernel-valid promoted artifacts as part of the readiness bar.

## Boundary With Rust And Web

Rust and web should reflect the kernel, not redefine it.

That means:

- kernel schema and validation rules belong in the CLI
- Rust may expose kernel views, prompts, or editing affordances
- web may expose kernel-backed artifact cards and review surfaces
- neither Rust nor web should invent competing kernel semantics

This follows the same boundary already established for link, session, runner,
and governance truth.

## First Implementation Slice

The right v0.1 implementation slice is intentionally small.

### Phase 1

- add this design note
- add a machine-readable kernel schema in `spec/v1/kernel.schema.json`
- define typed artifact classes and required fields

### Phase 2

- allow optional kernel blocks in process artifacts
- expose kernel validation results in run artifacts and packets
- make `structure_kernel` a real validation lane in `gate`

### Phase 3

- add explicit CLI surfaces such as:
  - `orp kernel validate`
  - `orp kernel explain`
  - `orp kernel promote`

These should be optional helpers, not mandatory user-facing prompt wrappers.

## Design Discipline

The kernel should enter ORP operationally, not metaphysically.

Start with:

- a small number of artifact classes
- a small number of required fields
- a promotion test
- clear validation semantics

Do not begin by trying to encode all human reasoning.

## Canonical Statement

The clean ORP statement for this model is:

The ORP Reasoning Kernel defines the shape of truth, while canonical artifacts
remain the source of truth.

Or, in product language:

Natural language at the boundary. Kernel structure at promotion. Canonical
artifacts at the core.
