# ORP Reasoning Kernel Evolution

This document defines how the ORP kernel should get stronger over time without
becoming slippery.

## Core Rule

The kernel should be:

- stable as a contract
- adaptive through governed evolution
- never silently rewritten by agents on the fly

Short form:

- stable core
- observable pressure
- explicit evolution

## What Should Stay Stable

The current core kernel remains the canonical source of truth for:

- artifact classes
- required-field rules
- hard vs soft promotion behavior
- machine-readable kernel validation in `RUN.json`

Those semantics live in:

- [spec/v1/kernel.schema.json](/Volumes/Code_2TB/code/orp/spec/v1/kernel.schema.json)
- [cli/orp.py](/Volumes/Code_2TB/code/orp/cli/orp.py)

The kernel should not self-mutate from a single chat, a single agent guess, or
one repo’s habits.

## What Should Evolve

The kernel should evolve from evidence about real use:

- repeated missing fields
- repeated field invention
- repeated continuation failures
- recurring requests for the same extra structure
- extension fields that become broadly useful

That evidence should shape proposals and migrations, not rewrite the core
implicitly.

## CLI Surfaces

ORP now exposes three explicit kernel-evolution surfaces:

### `orp kernel stats`

Observe real kernel-validation pressure from `RUN.json` artifacts.

Use it to answer questions like:

- which fields are repeatedly missing?
- which artifact classes fail most often?
- where is the current kernel strained in live repo usage?

### `orp kernel propose`

Scaffold a governed kernel-evolution proposal artifact.

Use it for changes like:

- adding a field
- introducing a new artifact class
- changing a requirement
- deprecating an old field

Proposal shape is governed by:

- [spec/v1/kernel-proposal.schema.json](/Volumes/Code_2TB/code/orp/spec/v1/kernel-proposal.schema.json)

### `orp kernel migrate`

Rewrite an artifact into the current canonical field order and schema version.

Use it to:

- normalize older artifacts
- apply explicit schema-version upgrades
- preserve stable truth while the kernel evolves

## Extensions

The best place for new pressure to land first is usually not the core kernel.
It should begin as an extension or proposal before becoming universal.

Extension shape is defined in:

- [spec/v1/kernel-extension.schema.json](/Volumes/Code_2TB/code/orp/spec/v1/kernel-extension.schema.json)

That gives ORP a place to trial domain-specific structure without forcing it
into every project prematurely.

## Recommended Kernel Evolution Loop

1. Observe pressure with `orp kernel stats`
2. Write an explicit proposal with `orp kernel propose`
3. Test the proposal against benchmark corpus and live agent pickup/continuation
4. If accepted, version the schema deliberately
5. Normalize older artifacts with `orp kernel migrate`
6. Protect the committed evidence package with CI threshold checks

## Non-Goal

The kernel should not become a hidden adaptive prompt system that silently
changes what truth means.

The repository should always be able to answer:

- which kernel version is in effect?
- why was it changed?
- what evidence justified the change?
- how do older artifacts migrate safely?

That is the ORP standard for a living protocol: dynamic in evidence, explicit
in truth.
