# ORP Reasoning Kernel Agent Pilot

This document records the first live in-environment Codex pickup simulation for
the ORP Reasoning Kernel.

Supporting artifact:

- [docs/benchmarks/orp_reasoning_kernel_agent_pilot_v0_1.json](./benchmarks/orp_reasoning_kernel_agent_pilot_v0_1.json)

Supporting corpus and harness:

- [examples/kernel/comparison/comparison-corpus.json](../examples/kernel/comparison/comparison-corpus.json)
- [scripts/orp-kernel-agent-pilot.py](../scripts/orp-kernel-agent-pilot.py)

## What This Pilot Measures

This pilot asks a real fresh Codex session to act like a downstream handoff
consumer with no repo context.

For each matched case and condition, the agent sees only the artifact and must
recover the **full required field set** for that artifact class:

- `task`: `object`, `goal`, `boundary`, `constraints`, `success_criteria`
- `decision`: `question`, `chosen_path`, `rejected_alternatives`, `rationale`, `consequences`
- `hypothesis`: `claim`, `boundary`, `assumptions`, `test_path`, `falsifiers`
- `experiment`: `objective`, `method`, `inputs`, `outputs`, `evidence_expectations`, `interpretation_limits`
- `checkpoint`: `completed_unit`, `current_state`, `risks`, `next_handoff_target`, `artifact_refs`
- `policy`: `scope`, `rule`, `rationale`, `invariants`, `enforcement_surface`
- `result`: `claim`, `evidence_paths`, `status`, `interpretation_limits`, `next_follow_up`

The agent is instructed to use `null` unless a field is explicit enough to
carry forward into a canonical artifact without invention.

This is a stronger standard than the earlier deterministic pickup proxy because
it uses an actual fresh Codex session rather than a local rubric only.

## What This Is And Is Not

This is a **live internal agent simulation**, not a human handoff study.

It does **not** prove:

- human pickup speed
- human clarification count
- downstream implementation quality
- cross-team or cross-model outcome superiority

It **does** prove something narrower and important:

- how much of the kernel’s required structure remains explicitly recoverable to
  a fresh downstream agent
- whether the kernel’s structural advantages survive contact with a real agent,
  not just a deterministic local scorer

## Current Result

On the matched `7`-case, `5`-domain live Codex corpus, the current report
shows:

- kernel mean pickup score: `1.000`
- generic checklist mean pickup score: `0.810`
- free-form mean pickup score: `0.695`

Pairwise result:

- kernel beats free-form on `7/7` cases
- kernel beats generic checklist on `4/7` cases and ties on `3/7`
- generic checklist beats free-form on average, but with `1` loss and `2` ties

Additional result:

- kernel keeps all required fields explicitly recoverable on the matched corpus
- kernel mean invention rate: `0.000`
- free-form and generic checklist both leave recoverability gaps for at least
  some artifact classes

## Why This Matters

This pilot matters because it is the first evidence layer that uses a real
fresh agent rather than only local deterministic scoring.

That gives us a stronger internal claim:

- the kernel’s structural advantage is not decorative
- the advantage remains visible to a downstream Codex session
- the benefit is strongest against free-form artifacts
- the generic checklist baseline is helpful, but it does not match the kernel’s
  full recoverability

The generic-checklist result is especially useful because it is **not** a
strawman. It performs reasonably well and even ties the kernel on some cases.
That makes the kernel’s wins more credible.

## Honest Caveat

This pilot still does not seal the kernel as a universally outcome-superior
methodology.

It is stronger than the earlier deterministic proxy, but it remains:

- internal
- model-specific
- artifact-recoverability-focused

The next real evidence bar is still:

- blinded human pickup studies
- downstream execution or review studies
- broader cross-model or cross-team replication

## Bottom Line

The live agent pilot makes the kernel materially harder to dismiss.

We now have evidence across three levels:

- deterministic structural comparison
- deterministic pickup proxy
- live fresh-agent recoverability simulation

Together, those support a strong internal claim:

ORP kernel artifacts preserve more explicit canonical structure for downstream
agents than free-form artifacts, and more than a generic checklist on average,
while keeping full required-field recoverability on the matched corpus.
