# ORP Reasoning Kernel Comparison Pilot

This document records the first in-repo side-by-side comparison between three
artifact styles:

1. free-form artifact writing
2. generic checklist artifact writing
3. ORP typed kernel artifact writing

Supporting artifact:

- [docs/benchmarks/orp_reasoning_kernel_comparison_v0_1.json](./benchmarks/orp_reasoning_kernel_comparison_v0_1.json)

Supporting corpus and harness:

- [examples/kernel/comparison/comparison-corpus.json](../examples/kernel/comparison/comparison-corpus.json)
- [scripts/orp-kernel-comparison.py](../scripts/orp-kernel-comparison.py)

## What This Pilot Measures

This pilot is intentionally narrow.

It does **not** measure downstream execution quality, human review outcomes, or
team handoff performance directly.

It **does** measure structural clarity on a matched internal corpus using a
deterministic rubric.

Each condition is scored on:

- artifact type clarity
- objective clarity
- limits clarity
- evaluation clarity
- handoff readiness
- class-specific completeness

The corpus spans:

- `7` cases
- `5` domains
- all `7` v0.1 kernel artifact classes

## Why This Comparison Matters

The current technical validation package proves that the kernel works.

What it did not yet prove by itself was whether the kernel offers more usable
structure than simpler alternatives on the same prompts.

This pilot addresses that specific gap by comparing matched artifacts instead
of evaluating the kernel in isolation.

## Current Result

On the matched internal corpus, the current report shows:

- kernel mean total score: `1.000`
- generic checklist mean total score: `0.687`
- free-form mean total score: `0.275`

Pairwise result:

- kernel beats generic checklist on all `7/7` cases
- kernel beats free-form on all `7/7` cases
- generic checklist beats free-form on all `7/7` cases

Additional result:

- kernel class-specific completeness mean: `1.000`
- generic checklist class-specific completeness mean: `0.657`
- free-form class-specific completeness mean: `0.328`

## What This Supports

This pilot supports a **narrow but real** claim:

On a matched internal comparison corpus, ORP kernel artifacts preserve more
explicit structural coverage than both free-form artifacts and a generic
checklist alternative.

That is stronger than a pure rationale-only claim.

## What This Does Not Yet Support

This pilot does **not** prove that the kernel:

- improves downstream implementation success
- improves human pickup speed in live handoffs
- reduces rework in actual projects
- is universally superior across all teams or domains

Those still require the larger studies in
[docs/ORP_REASONING_KERNEL_EVALUATION_PLAN.md](./ORP_REASONING_KERNEL_EVALUATION_PLAN.md).

## Why The Scoring Is Structured This Way

The scoring deliberately rewards explicit structure rather than latent meaning
buried in prose.

That reflects the actual ORP goal:

- humans can stay loose at the boundary
- but promotable repository artifacts should remain structurally legible

So this pilot is not a writing-style contest. It is a test of how much
canonically useful structure survives into the artifact itself.

## Bottom Line

This comparison pilot does not seal the kernel as a universally outcome-better
methodology.

It does provide the first comparative evidence that the kernel is not only
valid in isolation, but also materially stronger as a structural artifact
surface than the simpler alternatives tested here.
