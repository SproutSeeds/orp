# ORP Reasoning Kernel Evidence Matrix

This document separates what the ORP Reasoning Kernel currently proves from
what it only suggests.

Its purpose is to prevent the kernel from being over-claimed. The kernel is
stronger when we can say, precisely:

- what is already validated
- what is only partially supported
- what is still unproven
- what experiment would close the gap

Supporting references:

- [docs/ORP_REASONING_KERNEL_V0_1.md](/Volumes/Code_2TB/code/orp/docs/ORP_REASONING_KERNEL_V0_1.md)
- [docs/ORP_REASONING_KERNEL_TECHNICAL_VALIDATION.md](/Volumes/Code_2TB/code/orp/docs/ORP_REASONING_KERNEL_TECHNICAL_VALIDATION.md)
- [docs/benchmarks/orp_reasoning_kernel_v0_1_validation.json](/Volumes/Code_2TB/code/orp/docs/benchmarks/orp_reasoning_kernel_v0_1_validation.json)

## Evidence Grades

- `A`
  Directly supported by shipped implementation, tests, and repeatable benchmark
  evidence in this repo.
- `B`
  Strongly supported by implementation behavior and design logic, but still
  missing comparative or external validation.
- `C`
  Plausible and well-motivated, but not yet measured directly.
- `D`
  Strategic aspiration only. No meaningful validation yet.

## What Is Sealed For v0.1

These claims are strong enough to treat as validated implementation truths for
the current kernel release.

| Claim | Grade | Current Evidence | Why It Matters |
| --- | --- | --- | --- |
| ORP has a real typed kernel artifact surface. | A | [spec/v1/kernel.schema.json](/Volumes/Code_2TB/code/orp/spec/v1/kernel.schema.json), [cli/orp.py](/Volumes/Code_2TB/code/orp/cli/orp.py) | The kernel is not just prose. It is an enforceable CLI surface. |
| `orp init` seeds a valid starter kernel artifact and validates it in the default flow. | A | [tests/test_orp_init.py](/Volumes/Code_2TB/code/orp/tests/test_orp_init.py), [docs/benchmarks/orp_reasoning_kernel_v0_1_validation.json](/Volumes/Code_2TB/code/orp/docs/benchmarks/orp_reasoning_kernel_v0_1_validation.json) | New repos get the kernel by default instead of needing manual adoption. |
| All seven v0.1 artifact classes can scaffold and validate successfully. | A | [tests/test_orp_kernel.py](/Volumes/Code_2TB/code/orp/tests/test_orp_kernel.py), [docs/benchmarks/orp_reasoning_kernel_v0_1_validation.json](/Volumes/Code_2TB/code/orp/docs/benchmarks/orp_reasoning_kernel_v0_1_validation.json) | The kernel is broad enough for multiple project artifact types. |
| Hard mode blocks invalid promotable artifacts. | A | [tests/test_orp_kernel.py](/Volumes/Code_2TB/code/orp/tests/test_orp_kernel.py), [docs/benchmarks/orp_reasoning_kernel_v0_1_validation.json](/Volumes/Code_2TB/code/orp/docs/benchmarks/orp_reasoning_kernel_v0_1_validation.json) | ORP can enforce structural promotion standards rather than only advising. |
| Soft mode records invalidity without blocking work. | A | [tests/test_orp_kernel.py](/Volumes/Code_2TB/code/orp/tests/test_orp_kernel.py), [docs/benchmarks/orp_reasoning_kernel_v0_1_validation.json](/Volumes/Code_2TB/code/orp/docs/benchmarks/orp_reasoning_kernel_v0_1_validation.json) | ORP can stay fluid at intake while still surfacing missing structure. |
| Existing `structure_kernel` gates remain compatible when no explicit kernel config is present. | A | [tests/test_orp_kernel.py](/Volumes/Code_2TB/code/orp/tests/test_orp_kernel.py), [docs/benchmarks/orp_reasoning_kernel_v0_1_validation.json](/Volumes/Code_2TB/code/orp/docs/benchmarks/orp_reasoning_kernel_v0_1_validation.json) | The kernel does not silently break earlier ORP configurations. |
| One-shot local kernel CLI operations are within human-scale latency on the reference machine. | A | [scripts/orp-kernel-benchmark.py](/Volumes/Code_2TB/code/orp/scripts/orp-kernel-benchmark.py), [docs/benchmarks/orp_reasoning_kernel_v0_1_validation.json](/Volumes/Code_2TB/code/orp/docs/benchmarks/orp_reasoning_kernel_v0_1_validation.json) | The kernel is operationally lightweight enough to use during normal work. |

## What Is Strong But Not Fully Sealed

These claims are directionally convincing, but still need comparative or
broader validation before they should be presented as fully proven.

| Claim | Grade | Current Evidence | Missing Evidence | Best Next Experiment |
| --- | --- | --- | --- | --- |
| The seven chosen artifact classes are a good universal first set. | B | Cross-domain rationale in [docs/ORP_REASONING_KERNEL_TECHNICAL_VALIDATION.md](/Volumes/Code_2TB/code/orp/docs/ORP_REASONING_KERNEL_TECHNICAL_VALIDATION.md) and passing roundtrip coverage | Real corpus coverage across multiple project types | Cross-domain corpus fit study |
| The kernel reduces accidental chat-to-truth drift. | B | ORP’s promotion model and hard/soft gate behavior | Before/after repo evidence showing fewer ambiguous promotable artifacts | Comparative artifact hygiene study |
| The kernel is better than a generic checklist. | B | Typed classes give stronger semantic requirements than one generic field list | Direct comparison against a generic checklist baseline | Structured baseline comparison |
| The kernel is better than free-form artifact writing alone. | B | Implementation logic is strong and promotion semantics exist | Outcome comparison on real artifacts and reviewers | Free-form vs kernel artifact review study |
| The kernel can scale across agents and handoffs. | B | Machine-checkable artifacts and visible run traces | Multi-operator pickup data | Handoff pickup experiment |

## What Is Still Unproven

These are important claims, but they should not be stated as established fact
yet.

| Claim | Grade | Why It Is Not Yet Proven | What Would Prove It |
| --- | --- | --- | --- |
| Kernel use improves downstream project outcomes. | D | No controlled comparison yet between kernel and non-kernel workflows | Comparative study over real tasks with outcome scoring |
| Kernel-aware agents produce better work than agents without kernel structure. | D | No A/B benchmark on identical prompts and acceptance criteria | Agent benchmark across matched tasks |
| Kernel warnings correlate with later rework or quality failures. | D | No operational data collection yet | Longitudinal study on soft-mode warnings vs later edits |
| The current class set is close to optimal. | D | No competing class-model comparison or pruning study | Corpus analysis plus ablation tests |
| The kernel is equally suitable across software, research, ops, and writing domains. | C | Good rationale, but no multi-domain comparative evidence yet | Cross-domain corpus and reviewer study |

## Research Questions That Matter Most

If we want to move from “technically valid” to “research-grade validated,” the
highest-value questions are:

1. Does the kernel reduce ambiguity relative to free-form project artifacts?
2. Does the kernel improve handoff pickup quality for humans and agents?
3. Does the kernel improve downstream implementation or review success?
4. Is the typed class model actually better than a simpler generic checklist?
5. Where does the current class set fail across real project domains?

## Recommended Public Wording Right Now

These are safe claims now:

- ORP ships a typed reasoning-kernel artifact layer.
- ORP can scaffold, validate, and gate promotable kernel artifacts.
- ORP supports hard and soft promotion semantics for kernel validation.
- ORP includes repeatable benchmark evidence for the current implementation.

These should still be framed as goals or hypotheses:

- the kernel improves project outcomes
- the kernel is superior to other artifact-structuring approaches
- the current class set is the right final ontology

## Bottom Line

The kernel is sealed for `v0.1` as an implementation and protocol surface.

It is not yet sealed as a universally outcome-superior project methodology.

That is a good place to be if we stay explicit about the difference.
