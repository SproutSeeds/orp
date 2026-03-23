# ORP Reasoning Kernel Pickup Pilot

This document records the first in-repo pickup and handoff proxy for the ORP
Reasoning Kernel.

Supporting artifact:

- [docs/benchmarks/orp_reasoning_kernel_pickup_v0_1.json](/Volumes/Code_2TB/code/orp/docs/benchmarks/orp_reasoning_kernel_pickup_v0_1.json)

Supporting corpus and harness:

- [examples/kernel/comparison/comparison-corpus.json](/Volumes/Code_2TB/code/orp/examples/kernel/comparison/comparison-corpus.json)
- [scripts/orp-kernel-pickup.py](/Volumes/Code_2TB/code/orp/scripts/orp-kernel-pickup.py)

## What This Pilot Measures

This pilot measures **explicit pickup readiness** on a matched internal corpus.

For each artifact class, it asks whether a downstream operator could recover
the class-specific pickup targets directly from the artifact itself.

Examples:

- `task`
  - object
  - constraints
  - success criteria
- `decision`
  - question
  - chosen path
  - consequences
- `checkpoint`
  - current state
  - risks
  - next handoff target

The pilot compares:

1. free-form artifact writing
2. generic checklist artifact writing
3. ORP typed kernel artifact writing

## What This Is And Is Not

This is a **pickup proxy**, not a full live handoff study.

It does **not** prove:

- time-to-understanding with real operators
- clarification count under live review
- downstream execution quality

It **does** prove something narrower and still valuable:

how much pickup-critical information remains explicitly recoverable in the
artifact itself.

## Current Result

On the matched internal corpus, the current report shows:

- kernel mean pickup score: `1.000`
- generic checklist mean pickup score: `0.743`
- free-form mean pickup score: `0.452`

Pairwise result:

- kernel beats generic checklist on `7/7` cases
- kernel beats free-form on `7/7` cases
- generic checklist beats free-form on `7/7` cases

Additional result:

- kernel keeps all pickup targets explicitly answerable on the matched corpus

## Why This Matters

This pilot strengthens the kernel story in a way the pure structure benchmark
could not.

The earlier comparison pilot showed that kernel artifacts are structurally
fuller than the simpler alternatives.

This pickup pilot shows that the added structure is not decorative. It turns
into directly recoverable handoff value.

That is important because ORP is not trying to optimize for pretty artifacts.
It is trying to optimize for artifacts that another human or agent can pick up
and continue without confusion.

## Honest Caveat

This pilot still does not seal the kernel as a universally outcome-superior
methodology.

It is stronger evidence than a rationale-only claim, but it remains an
internal, deterministic proxy. The next step after this is still a live
human/agent pickup study as described in
[docs/ORP_REASONING_KERNEL_EVALUATION_PLAN.md](/Volumes/Code_2TB/code/orp/docs/ORP_REASONING_KERNEL_EVALUATION_PLAN.md).

## Bottom Line

The pickup pilot makes the kernel harder to dismiss.

We now have evidence that on a matched internal corpus, kernel artifacts do
not just score as more structured. They also preserve more explicit handoff
value than free-form and generic checklist alternatives.
