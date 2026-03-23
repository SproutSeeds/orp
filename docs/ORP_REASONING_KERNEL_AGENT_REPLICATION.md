# ORP Reasoning Kernel Agent Replication

This document records the completed `10`-repeat full-corpus repeatability
pilot for the live ORP kernel agent evaluation.

Supporting artifact:

- [docs/benchmarks/orp_reasoning_kernel_agent_replication_v0_2.json](/Volumes/Code_2TB/code/orp/docs/benchmarks/orp_reasoning_kernel_agent_replication_v0_2.json)

Supporting harness:

- [scripts/orp-kernel-agent-replication.py](/Volumes/Code_2TB/code/orp/scripts/orp-kernel-agent-replication.py)

The harness now supports:

- per-field stability tables
- progress reporting for long runs
- shard-and-merge execution for higher-repeat studies
- confidence-interval reporting for repeated live runs

## What This Measures

The original live agent pilot showed that a fresh Codex session could recover
the kernel’s required fields more completely than the simpler alternatives.

This replication harness asks a different question:

- does that result survive across repeated fresh-agent runs?

The current completed pilot covers:

- the full matched `7`-case corpus
- `10` independent fresh Codex repetitions of that corpus

## Current Result

Across the repeated full matched corpus:

- kernel mean pickup score: `1.000`
- generic checklist mean pickup score: `0.790`
- free-form mean pickup score: `0.718`

Stability result:

- kernel stayed above checklist on all `10/10` run-level repeats
- kernel stayed above free-form on all `10/10` run-level repeats
- kernel won `47/70` case-level comparisons against checklist and tied the other `23/70`
- kernel won `70/70` case-level comparisons against free-form
- kernel invention rate remained `0.000` across all `10` repeats

Confidence and stability result:

- kernel pickup CI95 half-width: `0.000`
- generic checklist pickup CI95 half-width: `0.023`
- free-form pickup CI95 half-width: `0.007`
- kernel per-field stability gap stayed at `0.000` for every tracked required field

The per-field tables are especially useful because they show where the simpler
alternatives still degrade under repetition:

- checklist repeatedly misses `decision.question` and `decision.rationale`
- checklist repeatedly misses `experiment.inputs`, `experiment.outputs`, and `hypothesis.falsifiers`
- checklist still struggles with `policy.enforcement_surface` and `task.object`
- free-form most often drops `experiment.outputs`, `result.evidence_paths`, and sometimes `checkpoint.next_handoff_target`

## Why This Matters

The replication pilot is now much stronger than a single-case smoke, because
it covers the full matched corpus, repeats it `10` times with fresh sessions,
and exposes field-level stability instead of only overall means.

That strengthens the evidence story in an agent-first way:

- the kernel advantage can survive fresh-session variation
- the kernel continues to look safe on invention
- the checklist baseline is helpful, but it still leaves repeatable structural
  holes that the kernel does not

## Honest Boundary

This is now a strong internal replication pilot, but it is still not a final
external replication study.

What remains:

- compare multiple agent models when practical
- run blinded human or mixed human/agent handoff replications
- extend the repeated continuation benchmark in the same style

## Bottom Line

The replication pilot makes the live agent story much more credible:

the kernel’s recoverability advantage appears stable under repeated fresh-agent
execution across the full matched corpus, not only on a single representative
case, and its field-level stability now looks materially cleaner than both
free-form and checklist alternatives.
