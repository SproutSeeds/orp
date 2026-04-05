# ORP Autonomy Project Compilation Model

## Purpose

Define the product model for turning a real repo with specs, roadmap docs, and
code into an autonomous ORP lane that runs until a true human gate.

This is the missing bridge between:

- "the roadmap exists"
- and "the agent can actually keep going unattended"

## Core Claim

ORP should not require users to manually hand-build a runtime registry before
autonomy becomes useful.

Instead, ORP should:

1. scan the project's authority surfaces
2. infer what work is already executable
3. identify what still requires human judgment or real-world action
4. scaffold the missing runtime contracts
5. run the admissible work until a true stop gate

## The Problem This Solves

In real projects, a capable agent can often continue from:

- `AGENTS.md`
- roadmap/spec documents
- active notes
- codebase scripts and commands

But an unattended runtime cannot rely on implicit operator judgment.

The unattended system needs explicit answers to:

- what is the source of truth?
- what is a roadmap vs a pause policy?
- what step is next?
- what command actually runs that step?
- what output proves the step is done?
- what requires a human?

This model gives ORP a way to infer and scaffold those answers instead of
making the user encode them all by hand first.

## Core Concepts

### 1. Authority Surfaces

These are the repo objects that define what the project is allowed to treat as
planning authority.

Typical sources:

- `AGENTS.md`
- `llms.txt`
- roadmap/spec docs
- current frontier or "next step" notes
- state files
- package manifests
- scripts and make targets
- protocol docs

### 2. Coverage Map

ORP should build a row-by-row map of project nodes:

- already executable
- partially executable
- strategic only
- human gated

This is the bridge from roadmap language to runtime truth.

### 3. Runtime Unit

A roadmap node becomes runnable only when ORP can associate it with:

1. one recognized next-step surface
2. one concrete command or builder
3. expected outputs
4. verification/closeout
5. one stop-gate interpretation

### 4. True Human Gate

A true gate is not "the agent feels uncertain."

A true gate is a boundary like:

- spend or purchase
- outreach or counterparty contact
- provider/vendor selection with real consequences
- legal/oversight/compliance judgment
- external release
- claim-bearing promotion
- destructive irreversible action
- real-world biological/physical execution

## Proposed ORP Flow

### `orp autonomy scan`

Purpose:

- inspect the repo and identify the candidate authority surfaces

Outputs:

- authority stack
- route split if multiple roadmap families exist
- likely live frontier docs
- possible command/build surfaces

### `orp autonomy coverage`

Purpose:

- build the roadmap-to-runtime coverage matrix

Outputs:

- executable nodes
- partial nodes
- human-gated nodes
- missing compilation requirements

### `orp autonomy compile`

Purpose:

- scaffold runtime units for uncovered but admissible roadmap work

Outputs:

- task contracts
- mission contracts
- gate dossiers
- checkpoint/closeout contracts

### `orp autonomy run`

Purpose:

- execute the compiled lane until a true gate, no-runnable boundary, or failure

Behavior:

- derive next admissible task
- execute
- checkpoint
- refresh workspace state
- repeat
- stop only at true gates

### `orp autonomy gates`

Purpose:

- show active gates and what human decisions they require

Outputs:

- gate id
- exact trigger
- current packet/dossier
- safe parallel work

### `orp autonomy resume`

Purpose:

- reopen a paused lane after a human gate is explicitly approved

Outputs:

- resumed runtime context
- reopened next step
- continuation receipt

## Compilation Heuristics

ORP should infer aggressively but conservatively.

Good candidates for automatic compilation:

- builder scripts that emit canonical artifacts
- docs that use exact next-step language
- repeated checkpoint patterns
- task-specific notes with strong input/output structure

Bad candidates for automatic compilation:

- vague strategic narratives with no runnable command
- tasks that imply counterparty contact
- tasks that imply money
- steps that promote support-only outputs into authority

## What ORP Should Emit

For a real project, the compiled autonomy packet should include:

- authority surfaces
- roadmap hierarchy
- coverage matrix
- task registry
- mission queue
- stop-gate policy
- human dossier templates
- run-until-gate launch surface
- resume-after-gate surface

## Boundary Rule

ORP remains process/governance infrastructure.

It can compile, route, checkpoint, and pause.

It must not treat its own packets as scientific or operational evidence.
Evidence still lives in the repo's canonical artifacts.

## Example Pattern

The controller benchmark experiment surfaced the exact shape:

1. exploit public/support-only work fully
2. compile the remaining pre-outreach tasks
3. keep drafts unsent
4. stop only when the next step would actually contact a counterparty or spend
5. emit a gate dossier
6. resume only after the human opens that gate

That pattern is generalizable well beyond one biotech project.

## Success Criteria

This model is working when ORP can take a repo with real specs and roadmaps and
produce:

- one honest "what can be done autonomously?" map
- one honest "where do humans still matter?" map
- one runnable autonomous lane
- one clean pause packet at the first real human boundary

## One-Sentence Version

ORP should compile a project's real planning surfaces into an executable
autonomous lane that keeps going until the work reaches a true human gate,
instead of requiring users to hand-author the whole runtime first.
