# ORP Reasoning Kernel Continuation Pilot

This document records the first full-corpus live continuation pilot for the ORP
Reasoning Kernel.

Supporting artifact:

- [docs/benchmarks/orp_reasoning_kernel_continuation_v0_1.json](/Volumes/Code_2TB/code/orp/docs/benchmarks/orp_reasoning_kernel_continuation_v0_1.json)

Supporting harness:

- [scripts/orp-kernel-continuation-pilot.py](/Volumes/Code_2TB/code/orp/scripts/orp-kernel-continuation-pilot.py)

Related harder benchmark:

- [docs/ORP_REASONING_KERNEL_CANONICAL_CONTINUATION_PILOT.md](/Volumes/Code_2TB/code/orp/docs/ORP_REASONING_KERNEL_CANONICAL_CONTINUATION_PILOT.md)

## What This Pilot Measures

The earlier live agent pilot measured recoverability: can a fresh downstream
agent reconstruct the required kernel fields?

This continuation pilot asks a slightly different question:

- can a fresh downstream agent continue the work safely?

For each artifact, the agent must:

- propose a recommended next action
- identify handoff-critical fields to carry forward
- surface what is explicitly missing instead of inventing it

The scoring emphasizes:

- carry-forward coverage
- invention rate
- whether a concrete next action is present

This remains the softer downstream benchmark. The harder follow-on test is the
canonical continuation pilot, where the downstream agent must produce the next
full kernel task artifact rather than only a safe continuation.

## Current Result

On the matched `7`-case, `5`-domain live continuation corpus:

- kernel continuation score: `1.000`
- generic checklist continuation score: `0.984`
- free-form continuation score: `0.968`

Invention result:

- kernel invention rate: `0.000`
- generic checklist invention rate: `0.000`
- free-form invention rate: `0.048`

## Why This Matters

This pilot pushes the evaluation one step closer to real downstream agent work.

The continuation corpus suggests:

- the kernel clearly supports safer continuation than free-form artifacts
- the kernel slightly exceeds the generic checklist on continuation score at
  corpus level, while never doing worse on any matched case
- the kernel preserves a safety advantage by keeping invention at `0.000`

## Honest Boundary

This is now a real full-corpus pilot, but it is still not a full external
continuation study.

What remains:

- replicate across more fresh sessions
- compare additional agent models when practical
- extend from artifact continuation to fuller downstream execution quality

## Bottom Line

The continuation pilot strengthens the kernel in a well-rounded way:

it suggests the kernel is not only easier to recover, but also a strong and
safe surface for downstream agent continuation across the matched corpus, while
showing that a generic checklist remains competitive enough to be a meaningful
baseline rather than a strawman.
