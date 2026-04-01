# ORP Reasoning Kernel Canonical Continuation Pilot

This document records the first full-corpus live canonical continuation pilot
for the ORP Reasoning Kernel.

Supporting artifact:

- [docs/benchmarks/orp_reasoning_kernel_canonical_continuation_v0_1.json](./benchmarks/orp_reasoning_kernel_canonical_continuation_v0_1.json)

Supporting harness:

- [scripts/orp-kernel-canonical-continuation.py](../scripts/orp-kernel-canonical-continuation.py)

## What This Pilot Measures

The earlier continuation pilot asked whether a fresh downstream agent could
continue work safely in a general sense.

This harder pilot asks a more demanding question:

- can a fresh downstream agent turn the source artifact into the next canonical
  kernel task artifact?

For each source artifact, the agent must produce a real task-shaped follow-on
object with:

- `object`
- `goal`
- `boundary`
- `constraints`
- `success_criteria`

The benchmark then scores:

- field alignment against the expected next canonical task
- unsupported invention
- whether missing structure is reported explicitly instead of silently filled

## Current Result

On the matched `7`-case, `5`-domain live canonical continuation corpus:

- kernel mean total score: `0.738`
- generic checklist mean total score: `0.663`
- free-form mean total score: `0.484`

Invention result:

- kernel mean invention rate: `0.386`
- generic checklist mean invention rate: `0.495`
- free-form mean invention rate: `0.748`

Pairwise result:

- kernel beat free-form on `7/7` cases
- kernel beat generic checklist on `4/7` cases
- kernel tied generic checklist on `1/7` cases
- kernel lost to generic checklist on `2/7` cases

## Why This Matters

This pilot is stronger than the softer continuation benchmark because it asks
the downstream agent to produce a real canonical artifact rather than only a
safe next action.

The result is more discriminative:

- free-form falls off sharply once a real next artifact must be constructed
- checklist stays meaningfully competitive
- kernel still leads on aggregate score and invention control

That makes the evidence more believable, not less. The kernel is not winning
against a straw baseline here.

## Honest Boundary

The canonical continuation pilot does not prove universal methodological
superiority.

It does show a narrower and important result:

- kernel structure gives a fresh downstream agent a stronger base for producing
  the next canonical task artifact than free-form notes
- checklist can still be strong on some cases, so the kernel advantage is real
  but not absolute

What remains:

- repeat the canonical continuation benchmark across multiple fresh runs
- add per-field stability summaries for canonical continuation itself
- compare multiple models when practical

## Bottom Line

The harder continuation benchmark makes the kernel evidence more grounded:

the kernel still wins on average, stays safest on invention, and clearly beats
free-form when the downstream task is “produce the next canonical artifact,”
while revealing that a strong checklist baseline remains competitive enough to
matter on some cases.
