# ORP Reasoning Kernel Technical Validation

This document defines the ORP Reasoning Kernel in technical terms, explains
why ORP implements it this way, and records the initial validation evidence
for `v0.1`.

The supporting benchmark artifact for this document is:

- [docs/benchmarks/orp_reasoning_kernel_v0_1_validation.json](/Volumes/Code_2TB/code/orp/docs/benchmarks/orp_reasoning_kernel_v0_1_validation.json)

For the honest claim-by-claim evidence status and remaining research gaps, see:

- [docs/ORP_REASONING_KERNEL_EVIDENCE_MATRIX.md](/Volumes/Code_2TB/code/orp/docs/ORP_REASONING_KERNEL_EVIDENCE_MATRIX.md)
- [docs/ORP_REASONING_KERNEL_EVALUATION_PLAN.md](/Volumes/Code_2TB/code/orp/docs/ORP_REASONING_KERNEL_EVALUATION_PLAN.md)

## 1. Definition

The ORP Reasoning Kernel is the typed artifact grammar and validation layer
used by ORP to move work from free-form intent into canonical repository
artifacts.

It operates in three roles:

1. Interpreter
   Convert loose natural-language intent into a structured working shape.
2. Validator
   Check whether a candidate artifact is complete enough to be trusted and
   promoted.
3. Canonizer
   Gate whether the artifact can become repository truth and show its
   validation trace in ORP run output.

The kernel is implemented through:

- [spec/v1/kernel.schema.json](/Volumes/Code_2TB/code/orp/spec/v1/kernel.schema.json)
- `orp kernel scaffold`
- `orp kernel validate`
- `structure_kernel` gate enforcement in [cli/orp.py](/Volumes/Code_2TB/code/orp/cli/orp.py)

## 2. What Problem It Solves

Without a kernel layer, ORP can still execute work, but repository truth tends
to drift into one of two bad states:

1. Chat soup
   Important meaning lives in prompts and responses instead of canonical
   artifacts.
2. Hidden agent structure
   The agent may internally interpret a task well, but another human or agent
   cannot inspect that structure or validate promotion.

The kernel addresses that by making promotable artifacts:

- typed
- minimally complete
- machine-checkable
- reusable in handoffs
- visible in run artifacts

## 3. Why This Kernel Instead Of Another Approach

### A. Why not free-form markdown or chat alone?

Free-form text is useful for ideation, but it does not reliably answer:

- what kind of artifact this is
- what minimum structure is present or missing
- what should block promotion
- what another operator can trust later

ORP keeps natural language at the boundary and adds structure at promotion.

### B. Why not require kernel-native syntax for all human input?

Because that damages usability and adoption.

Humans should be able to think in normal language. ORP should not require
every prompt to be authored as a rigid schema object before work can happen.
That is why the kernel is enforced at the artifact and gate layer rather than
as a hard input parser for every message.

### C. Why typed artifact classes instead of one generic checklist?

Because a task, a decision, and a hypothesis fail in different ways.

A single universal checklist loses semantic meaning. ORP therefore uses typed
artifact classes with different required fields:

- `task`
- `decision`
- `hypothesis`
- `experiment`
- `checkpoint`
- `policy`
- `result`

This is enough structure to be useful without forcing a heavyweight ontology.

### D. Why not a domain-specific kernel for just software or just research?

Because ORP is meant to govern many kinds of work, not one domain.

The chosen artifact classes map across:

- software delivery
- research
- product design
- operations and reliability
- writing and knowledge work
- policy and governance work

### E. Why not a hidden agent-only kernel?

Because invisible structure cannot be audited.

If the agent interprets a request privately but the repository never records
that shape, then the kernel is not stabilizing truth. ORP instead writes
kernel validation into `RUN.json` and lets artifacts be validated directly
from the CLI.

### F. Why not a full ontology before shipping anything?

Because `v0.1` is meant to be operational, not metaphysical.

The current kernel is intentionally minimal:

- a small number of classes
- a small number of required fields
- explicit hard vs soft gate behavior
- compatibility with existing `structure_kernel` gates

That lowers rollout risk and makes the kernel easier to test and adopt.

## 4. The Current Technical Shape

### Artifact classes

The schema currently supports:

- `task`
- `decision`
- `hypothesis`
- `experiment`
- `checkpoint`
- `policy`
- `result`

Each class has a minimum required field set in:

- [kernel.schema.json](/Volumes/Code_2TB/code/orp/spec/v1/kernel.schema.json)
- [cli/orp.py](/Volumes/Code_2TB/code/orp/cli/orp.py)

### CLI operations

The kernel currently exposes:

- `orp kernel scaffold`
- `orp kernel validate`

### Gate integration

ORP now treats `structure_kernel` as a real validation lane when a gate
declares a `kernel` block. That gives:

- `soft` mode
  Validation issues are recorded but do not block the run.
- `hard` mode
  Validation issues fail the gate and block promotion.

Legacy `structure_kernel` gates without explicit `kernel` configuration remain
compatible.

### Bootstrap behavior

`orp init` now seeds a starter task artifact at:

- `analysis/orp.kernel.task.yml`

and the default profile validates it in hard mode.

## 5. Benchmark And Validation Method

The repeatable harness is:

- [scripts/orp-kernel-benchmark.py](/Volumes/Code_2TB/code/orp/scripts/orp-kernel-benchmark.py)

The harness benchmarks and validates:

1. Bootstrap path
   `orp init` -> starter artifact -> `orp kernel validate` -> `orp gate run`
2. Roundtrip path
   `orp kernel scaffold` + `orp kernel validate` for every artifact class
3. Enforcement path
   hard mode, soft mode, and legacy compatibility

The benchmark report was generated on:

- commit `5c87faf4fbd54d203cc0ca05683544355c306d55`
- package version `0.4.6`
- Python `3.9.6`
- Node `v24.10.0`
- `macOS-26.3-arm64-arm-64bit`

## 6. What The Benchmarks Show

### A. Bootstrap ergonomics

Reference run, 5 iterations:

- `orp init` mean: `245.958 ms`
- starter `orp kernel validate` mean: `165.837 ms`
- default `orp gate run` mean: `240.768 ms`

Interpretation:

- Kernel bootstrap is comfortably sub-second.
- The one-shot local developer experience is fast enough to be used in normal
  repo workflow without feeling heavy.
- These timings include the real `node -> python CLI` invocation path, which is
  the correct path to benchmark for npm-installed ORP use.

### B. Roundtrip across all artifact classes

All seven artifact classes successfully scaffolded and validated.

Observed means:

- scaffold mean: `157.864 ms`
- validate mean: `156.060 ms`

Interpretation:

- The kernel is not only task-shaped.
- The CLI surface is already general enough for multiple project artifact
  types.

### C. Enforcement semantics

Reference single-run timings:

- hard mode invalid artifact: `164.938 ms`, `FAIL`
- soft mode invalid artifact: `163.174 ms`, `PASS` with advisory invalid state
- legacy compatibility gate: `161.567 ms`, `PASS` without `kernel_validation`

Interpretation:

- hard mode and soft mode are enforced and testable
- existing `structure_kernel` surfaces do not regress when no explicit kernel
  config is present

## 7. Claims And Evidence

The benchmark report records five claims, all currently passing:

1. `starter_kernel_bootstrap`
   ORP seeds a valid starter artifact and a passing default kernel gate.
2. `typed_artifact_roundtrip`
   All seven artifact classes scaffold and validate successfully.
3. `promotion_enforcement_modes`
   Hard mode blocks invalid artifacts; soft mode records advisory invalidity.
4. `legacy_structure_kernel_compatibility`
   Older `structure_kernel` gates remain compatible.
5. `local_cli_kernel_ergonomics`
   One-shot kernel operations remain within human-scale local latency
   thresholds on the reference machine.

These claims are backed by:

- [tests/test_orp_kernel.py](/Volumes/Code_2TB/code/orp/tests/test_orp_kernel.py)
- [tests/test_orp_init.py](/Volumes/Code_2TB/code/orp/tests/test_orp_init.py)
- [tests/test_orp_kernel_benchmark.py](/Volumes/Code_2TB/code/orp/tests/test_orp_kernel_benchmark.py)
- [docs/benchmarks/orp_reasoning_kernel_v0_1_validation.json](/Volumes/Code_2TB/code/orp/docs/benchmarks/orp_reasoning_kernel_v0_1_validation.json)

## 8. Why This Applies To All Project Types

The kernel is not a software-only mechanism. It is a project-structure
mechanism.

### Software

- feature task
- architectural decision
- release policy
- implementation result

### Research

- hypothesis
- experiment
- result
- checkpoint

### Product and design

- task
- decision
- experiment
- result

### Operations and reliability

- policy
- checkpoint
- result
- task

### Writing and knowledge work

- task
- decision
- hypothesis
- result

The kernel applies because most serious projects need the same underlying
capabilities:

- define the object of work
- define boundaries and constraints
- promote only sufficiently structured truth
- preserve handoff-quality artifacts

## 9. Limits Of v0.1

The current kernel validates structural sufficiency, not semantic truth.

It can tell us:

- whether required fields are present
- whether an artifact is typed correctly
- whether promotion rules are satisfied
- whether a gate should block or advise

It cannot tell us:

- whether the task is strategically wise
- whether a hypothesis is scientifically correct
- whether a result interpretation is deeply valid
- whether the chosen artifact class was the best possible framing

That is an acceptable `v0.1` limitation. ORP is not trying to ship a truth
oracle. It is shipping a minimum structure standard for canonical work.

## 10. Bottom Line

The ORP Reasoning Kernel is technically justified because it gives ORP a
repeatable, inspectable, and enforceable way to turn natural-language project
intent into typed canonical artifacts.

The current evidence supports that claim:

- it boots cleanly in new repos
- it works across all current artifact classes
- it enforces hard vs soft promotion semantics correctly
- it preserves compatibility with pre-kernel `structure_kernel` gates
- it stays within human-scale local CLI latency targets

That makes it a good `v0.1` kernel: minimal, general, validated, and already
useful.
